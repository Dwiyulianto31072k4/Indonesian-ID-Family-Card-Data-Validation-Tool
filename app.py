import streamlit as st
import pandas as pd
import numpy as np
import openpyxl
import zipfile
import re
from datetime import datetime
import time
import io
import base64

st.set_page_config(
    page_title="Indonesian ID Data Validation Tool",
    page_icon="📋",
    layout="wide"
)

st.title("Indonesian ID & Family Card Data Validation Tool")

# Define helper functions
def is_valid_tempat_lahir(tempat_lahir, kota_indonesia):
    return tempat_lahir.upper() in kota_indonesia

def clean_data(raw_df, kota_indonesia):
    # Define criteria for clean data
    def is_valid_kk_no(kk_no):
        return isinstance(kk_no, str) and kk_no.isdigit() and len(kk_no) == 16 and kk_no[-4:] != '0000'

    def is_valid_nik(nik):
        return isinstance(nik, str) and nik.isdigit() and len(nik) == 16 and nik[-4:] != '0000'

    def is_valid_custname(custname):
        return isinstance(custname, str) and not any(c.isdigit() for c in custname)

    def is_valid_jenis_kelamin(jenis_kelamin):
        return jenis_kelamin in ['LAKI-LAKI','LAKI - LAKI','LAKI LAKI', 'PEREMPUAN']

    def is_valid_tempat_lahir(tempat_lahir):
        return isinstance(tempat_lahir, str) and tempat_lahir.upper() in kota_indonesia

    def is_valid_date(date_str):
        if isinstance(date_str, str):
            try:
                date_obj = datetime.strptime(date_str, '%d/%m/%Y')
                if date_obj.date() <= datetime.today().date():
                    return True
                else:
                    return False
            except ValueError:
                return False
        elif isinstance(date_str, pd.Timestamp):
            if date_str.date() <= datetime.today().date():
                return True
            else:
                return False
        else:
            return False

    # Initialize the Check_Desc column with empty strings
    raw_df['Check_Desc'] = ''

    # Apply criteria to filter clean data
    valid_kk_no = raw_df['KK_NO'].apply(is_valid_kk_no)
    valid_nik = raw_df['NIK'].apply(is_valid_nik)
    valid_custname = raw_df['CUSTNAME'].apply(is_valid_custname)
    valid_jenis_kelamin = raw_df['JENIS_KELAMIN'].apply(is_valid_jenis_kelamin)
    valid_tempat_lahir = raw_df['TEMPAT_LAHIR'].apply(is_valid_tempat_lahir)
    valid_tanggal_lahir = raw_df['TANGGAL_LAHIR'].apply(is_valid_date)

    clean_df = raw_df[valid_kk_no & valid_nik & valid_custname & valid_jenis_kelamin & valid_tempat_lahir & valid_tanggal_lahir]

    # Identify issues in the data
    raw_df.loc[~valid_kk_no, 'Check_Desc'] += raw_df.loc[~valid_kk_no, 'KK_NO'].apply(
        lambda x: f'Invalid KK_NO (length: {len(str(x))}, digits only: {str(x).isdigit()}, last_digits: {str(x)[-4:]}); '
    )
    raw_df.loc[~valid_nik, 'Check_Desc'] += raw_df.loc[~valid_nik, 'NIK'].apply(
        lambda x: f'Invalid NIK (length: {len(str(x))}, digits only: {str(x).isdigit()}, last_digits: {str(x)[-4:]}); '
    )
    raw_df.loc[~valid_custname, 'Check_Desc'] += raw_df.loc[~valid_custname, 'CUSTNAME'].apply(
        lambda x: f'Invalid CUSTNAME (contains special characters or digits: {x}); '
    )
    raw_df.loc[~valid_jenis_kelamin, 'Check_Desc'] += raw_df.loc[~valid_jenis_kelamin, 'JENIS_KELAMIN'].apply(
        lambda x: f'Invalid JENIS_KELAMIN (value: {x}); '
    )
    raw_df.loc[~valid_tempat_lahir, 'Check_Desc'] += raw_df.loc[~valid_tempat_lahir, 'TEMPAT_LAHIR'].apply(
        lambda x: f'Invalid TEMPAT_LAHIR (value: {str(x)}); '
    )
    raw_df.loc[~valid_tanggal_lahir, 'Check_Desc'] += raw_df.loc[~valid_tanggal_lahir, 'TANGGAL_LAHIR'].apply(
        lambda x: f'Invalid TANGGAL_LAHIR (value: {str(x)}, expected format DD/MM/YYYY); '
    )
    
    # All other rows are considered messy data
    messy_df = raw_df[raw_df['Check_Desc'] != '']

    # Remove the Check_Desc column from the clean_df
    clean_df = clean_df.drop(columns=['Check_Desc'])

    return messy_df, clean_df

def create_download_link(df, filename, text):
    """Generate a link to download the DataFrame as an Excel file"""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    
    b64 = base64.b64encode(output.getvalue()).decode()
    href = f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="{filename}">{text}</a>'
    return href

def generate_summary_excel(messy_df, clean_df, total_data):
    """Generate Excel with summary and both datasets"""
    output = io.BytesIO()
    
    # Calculate statistics
    messy_data = len(messy_df)
    clean_data = len(clean_df)
    
    num_rows, num_cols = messy_df.shape
    len_param = num_cols - 1
    
    invalid_kk = len(messy_df[messy_df['Check_Desc'].str.contains('Invalid KK_NO')])
    invalid_nik = len(messy_df[messy_df['Check_Desc'].str.contains('Invalid NIK')])
    invalid_name = len(messy_df[messy_df['Check_Desc'].str.contains('Invalid CUSTNAME')])
    invalid_gender = len(messy_df[messy_df['Check_Desc'].str.contains('Invalid JENIS_KELAMIN')])
    invalid_places = len(messy_df[messy_df['Check_Desc'].str.contains('Invalid TEMPAT_LAHIR')])
    invalid_date = len(messy_df[messy_df['Check_Desc'].str.contains('Invalid TANGGAL_LAHIR')])
    
    total_invalid = len(messy_df) * len_param
    messy_invalid = invalid_kk + invalid_nik + invalid_name + invalid_gender + invalid_places + invalid_date
    clean_invalid = total_invalid - messy_invalid
    
    # Prepare summary data
    summary_headers = ["Category", "Total Data", "Messy Data", "Clean Data", "", "Invalid Parameter", "Clean Parameter", "Messy Parameter", "Invalid KK", "Invalid NIK", "Invalid Name", "Invalid Gender", "Invalid Places", "Invalid Date"]
    summary_counts = ["Data", total_data, messy_data, clean_data, "", total_invalid, clean_invalid, messy_invalid, invalid_kk, invalid_nik, invalid_name, invalid_gender, invalid_places, invalid_date]
    summary_percentages = ["Data (%)", 100.0, round(messy_data / total_data * 100, 2), round(clean_data / total_data * 100, 2), "", 100.0, round(clean_invalid / total_invalid * 100, 2), round(messy_invalid / total_invalid * 100, 2), round(invalid_kk / total_invalid * 100, 2), round(invalid_nik / total_invalid * 100, 2), round(invalid_name / total_invalid * 100, 2), round(invalid_gender / total_invalid * 100, 2), round(invalid_places / total_invalid * 100, 2), round(invalid_date / total_invalid * 100, 2)]
    
    summary_df = pd.DataFrame([summary_counts, summary_percentages], columns=summary_headers)
    
    # Create Excel file with multiple sheets
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        summary_df.to_excel(writer, sheet_name='Summary', index=False)
        messy_df.to_excel(writer, sheet_name='Messy Data', index=False)
        clean_df.to_excel(writer, sheet_name='Clean Data', index=False)
    
    return output.getvalue()

# Sidebar with information and upload
with st.sidebar:
    st.header("Upload Data")
    uploaded_excel = st.file_uploader("Upload your Excel file", type=['xlsx'])
    
    st.markdown("---")
    st.header("Upload City List (Optional)")
    uploaded_city_list = st.file_uploader("Upload a custom city list (CSV/TXT)", type=['csv', 'txt'])
    
    use_default_cities = st.checkbox("Use Default City List", value=True)
    
    st.markdown("---")
    st.subheader("About This Tool")
    st.info("""
    This tool validates Indonesian ID Card (NIK) and Family Card (KK) data.
    
    It checks:
    - KK_NO (16 digits, not ending with '0000')
    - NIK (16 digits, not ending with '0000')
    - Names (no digits)
    - Gender (standard formats)
    - Birth place (against city database)
    - Birth date (valid format and not future date)
    """)

# Main page content
if uploaded_excel is not None:
    start_time = time.time()
    
    # Load city reference data
    if uploaded_city_list and use_default_cities:
        st.warning("Both custom and default city lists selected. Using both.")
    
    # Default city list from your original code
    new_kota = [
    'ACEH BARAT', 'ACEH BESAR', 'ACEH TAMIANG', 'ACEH TIMUR', 'ACEH', 'AIR DINGIN ', 'AIR MOLEK',
    'AIR NANINGAN', 'AKEDAGA', 'AMBARAWA', 'AMBON', 'AMPENAN', 'ASAHAN', 'BAA ROTE', 'BAGOR',
    'BALAM', 'BALI', 'BALIGE', 'BALIKPAPAN', 'BALUNGAN', 'BANDA ACEH', 'BANDAR BETSY', 'BANDAR DALAM',
    'BANDAR LAMPUNG', 'BANDUNG BARAT', 'BANDUNG', 'BANGGAI', 'BANGKA BARAT', 'BANGKA', 'BANGKALAN',
    'BANJAR', 'BANJARMASIN', 'BANJARNEGARA', 'BANJARSARI', 'BANTAL', 'BANTARWARU', 'BANTEN', 'BANTUL',
    'BANYUASIN', 'BANYUMAS', 'BANYUWANGI', 'BARITO KUALA', 'BATAM', 'BATANG HARI', 'BATANG', 'BATOLA',
    'BATU KAMBING', 'BATURAJA', 'BATURSARI', 'BAYANG', 'BAYUNG LENCIR INDAH', 'BEKASI', 'BELAWAN ',
    'BELITANG', 'BELOPA', 'BENGKALIS', 'BENGKULU UTARA', 'BENGKULU', 'BERAU', 'BERGAS', 'BERINGIN JAYA',
    'BIAK', 'BIMA', 'BINJAI', 'BLITAR', 'BLORA', 'BOBOTSARI', 'BOGOR', 'BOJONEGORO', 'BONDOWOSO',
    'BOYOLALI', 'BREBES', 'BUAYAN', 'BUKABU', 'BUKIT TINGGI', 'BUMIAYU', 'BUNTU MAULI', 'CAHAYA NEGERI',
    'CAWAS', 'CENGAL', 'CEPU', 'CIAMIS', 'CIANJUR', 'CIKARANG', 'CILACAP', 'CILEGON', 'CIMAHI',
    'CIMANGGU', 'CIPUTAT', 'CIRACAP', 'CIREBON', 'CISAMPANG', 'DELI SERDANG', 'DEMAK', 'DENPASAR',
    'DEPOK', 'DONGGALA', 'DUKUH', 'DUMAI', 'DURI', 'ENDE', 'GADING', 'GARUT', 'GEGARANG', 'GEMARANG',
    'GENDING', 'GETASAN', 'GIRIWINANGUN', 'GOMBONG', 'GONDANG', 'GORONTALO', 'GRESIK', 'GROBOGAN',
    'GUNUNG KIDUL', 'GUNUNGKIDUL', 'GUNUNGPATI', 'GUNUNGSITOLI', 'HILIMBOWO', 'HILIWAEBU',
    'HILIZOROILAWA', 'HORISAN RANGGITGIT', 'HUTAMULA', 'INDRAGIRI HILIR', 'INDRAGIRI HULU',
    'INDRAGIRIHULU', 'INDRAMAYU', 'INDRAPURA', 'JABUNG', 'JAKARTA BARAT', 'JAKARTA PUSAT',
    'JAKARTA SELATAN', 'JAKARTA TIMUR', 'JAKARTA UTARA', 'JAKARTA', 'JAMBI', 'JATENG', 'JAWA TENGAH',
    'JAYAPURA', 'JEMBER', 'JEPARA', 'JOMBANG'
    # Truncated for brevity - you should include all cities from your original list
    ]
    
    # If using default city list
    kota_indonesia = []
    if use_default_cities:
        kota_indonesia = new_kota
    
    # If a custom city list is uploaded
    if uploaded_city_list:
        try:
            city_df = pd.read_csv(uploaded_city_list, delimiter=',')
            if 'CITY_DESC' in city_df.columns:
                # Process same as original code
                city_df['CITY_DESC'] = city_df['CITY_DESC'].str.replace('Kota ', '').str.replace('Kabupaten ', '').str.replace('Kab ', '')
                city_df['CITY_DESC'] = city_df['CITY_DESC'].str.upper()
                custom_cities = city_df['CITY_DESC'].tolist()
            else:
                # Assume simple list format
                custom_cities = [city.strip().upper() for city in city_df.iloc[:, 0].tolist()]
            
            kota_indonesia.extend(custom_cities)
            st.sidebar.success(f"Added {len(custom_cities)} cities from uploaded list")
        except Exception as e:
            st.sidebar.error(f"Error reading city list: {e}")
    
    if not kota_indonesia:
        st.error("No city list is available. Please use the default city list or upload a custom one.")
        st.stop()
    
    # Process the Excel file
    try:
        with st.spinner("Loading and processing data..."):
            # Read Excel file
            df_full = pd.DataFrame()
            excel_file = uploaded_excel
            
            # Read Excel workbook
            try:
                with pd.ExcelFile(excel_file) as xls:
                    sheet_names = xls.sheet_names
                    
                    for sheet in sheet_names:
                        try:
                            df = pd.read_excel(xls, sheet_name=sheet, dtype={'KK_NO_GROSS':object, 'KK_NO':object, 'NIK_GROSS':object, 'NIK':object})
                            df_full = pd.concat([df_full, df], ignore_index=True)
                        except Exception as e:
                            st.warning(f"Error reading sheet {sheet}: {e}")
            except Exception as e:
                st.error(f"Error opening Excel file: {e}")
                st.stop()
            
            # Check if we have data
            if df_full.empty:
                st.error("No data could be read from the Excel file.")
                st.stop()
            
            # Check for required columns
            required_columns = ['KK_NO', 'NIK', 'CUSTNAME', 'JENIS_KELAMIN', 'TANGGAL_LAHIR', 'TEMPAT_LAHIR']
            missing_columns = [col for col in required_columns if col not in df_full.columns]
            
            if missing_columns:
                st.error(f"Excel file is missing required columns: {', '.join(missing_columns)}")
                st.stop()
            
            # Prepare data for validation
            df_req = df_full.loc[:, required_columns].copy()
            df_req['KK_NO'] = df_req['KK_NO'].astype(str)
            df_req['NIK'] = df_req['NIK'].astype(str)
            
            # Try to convert dates - handle different formats
            try:
                df_req['TANGGAL_LAHIR'] = pd.to_datetime(df_req['TANGGAL_LAHIR'], format="%d/%m/%Y", errors='coerce')
            except:
                try:
                    df_req['TANGGAL_LAHIR'] = pd.to_datetime(df_req['TANGGAL_LAHIR'], errors='coerce')
                except:
                    st.warning("Could not parse date format. Treating as string.")
            
            # Run the validation
            messy_df, clean_df = clean_data(df_req, kota_indonesia)
            
            end_time = time.time()
            processing_time = end_time - start_time
            
            # Show stats
            total_data = len(df_req)
            clean_count = len(clean_df)
            messy_count = len(messy_df)
            
            st.success(f"Processing complete in {processing_time:.2f} seconds!")
            
            # Display statistics
            st.header("Validation Results")
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Records", total_data)
            col2.metric("Clean Records", clean_count, f"{clean_count/total_data*100:.1f}%")
            col3.metric("Messy Records", messy_count, f"{messy_count/total_data*100:.1f}%")
            
            # Error Type Analysis
            st.subheader("Error Analysis")
            error_stats = {
                "Invalid KK Numbers": len(messy_df[messy_df['Check_Desc'].str.contains('Invalid KK_NO')]),
                "Invalid NIK Numbers": len(messy_df[messy_df['Check_Desc'].str.contains('Invalid NIK')]),
                "Invalid Names": len(messy_df[messy_df['Check_Desc'].str.contains('Invalid CUSTNAME')]),
                "Invalid Gender": len(messy_df[messy_df['Check_Desc'].str.contains('Invalid JENIS_KELAMIN')]),
                "Invalid Birthplaces": len(messy_df[messy_df['Check_Desc'].str.contains('Invalid TEMPAT_LAHIR')]),
                "Invalid Birth Dates": len(messy_df[messy_df['Check_Desc'].str.contains('Invalid TANGGAL_LAHIR')])
            }
            
            # Create a bar chart
            error_df = pd.DataFrame({'Error Type': list(error_stats.keys()), 'Count': list(error_stats.values())})
            st.bar_chart(error_df.set_index('Error Type'))
            
            # Data previews
            tab1, tab2 = st.tabs(["Clean Data", "Messy Data"])
            
            with tab1:
                st.dataframe(clean_df)
                
            with tab2:
                st.dataframe(messy_df)
            
            # Download buttons
            st.header("Download Results")
            
            # Generate Excel with all data
            excel_data = generate_summary_excel(messy_df, clean_df, total_data)
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.download_button(
                    label="Download Full Report (Excel)",
                    data=excel_data,
                    file_name="data_validation_results.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            
            with col2:
                st.download_button(
                    label="Download Clean Data (CSV)",
                    data=clean_df.to_csv(index=False),
                    file_name="clean_data.csv",
                    mime="text/csv"
                )
                
    except Exception as e:
        st.error(f"An error occurred during processing: {str(e)}")
        st.exception(e)
else:
    # Display instructions when no file is uploaded
    st.header("How to Use This Tool")
    st.markdown("""
    1. Upload your Excel file containing ID and family card data
    2. Optionally upload a custom city list for birthplace validation
    3. View validation results and statistics
    4. Download clean data and validation reports
    
    ### Required Excel Column Headers
    Your Excel file should contain these columns:
    - `KK_NO` (Family Card Number)
    - `NIK` (National ID Number)
    - `CUSTNAME` (Person's Name)
    - `JENIS_KELAMIN` (Gender)
    - `TANGGAL_LAHIR` (Date of Birth)
    - `TEMPAT_LAHIR` (Place of Birth)
    
    ### Validation Rules
    - KK_NO: 16 digits, not ending with '0000'
    - NIK: 16 digits, not ending with '0000'
    - CUSTNAME: No digits allowed
    - JENIS_KELAMIN: Must be 'LAKI-LAKI', 'LAKI - LAKI', 'LAKI LAKI', or 'PEREMPUAN'
    - TEMPAT_LAHIR: Must match a city in the reference list
    - TANGGAL_LAHIR: Valid date in DD/MM/YYYY format, not in the future
    """)
    
    st.info("Please upload an Excel file to begin validation.")
