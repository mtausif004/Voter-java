import streamlit as st
import pandas as pd
import jpype
import jpype.imports
import sqlite3
import re
import os

# --- 1. ALL 64 DISTRICTS COMPLETE GEOGRAPHIC DATA (Verified Structure) ---
@st.cache_data
def load_bangladesh_complete_geo():
    """Google & GitHub source theke verified Bangladesh er 8 division o 64 district er master structure"""
    return {
        "Dhaka (ঢাকা)": [
            "Dhaka (ঢাকা)", "Gazipur (গাজীপুর)", "Narayanganj (নারায়ণগঞ্জ)", "Tangail (টাঙ্গাইল)",
            "Narsingdi (নরসিংদী)", "Manikganj (মানিকগঞ্জ)", "Munshiganj (মুন্সিগঞ্জ)", "Faridpur (ফরিদপুর)",
            "Madaripur (মাদারীপুর)", "Gopalganj (গোপালগঞ্জ)", "Rajbari (রাজবাড়ী)", "Shariatpur (শরীয়তপুর)", 
            "Kishoreganj (কিশোরগঞ্জ)"
        ],
        "Chattogram (চট্টগ্রাম)": [
            "Chattogram (চট্টগ্রাম)", "Cox's Bazar (কক্সবাজার)", "Cumilla (কুমিল্লা)", "Feni (ফেনী)",
            "Brahmanbaria (ব্রাহ্মণবাড়িয়া)", "Noakhali (নোয়াখালী)", "Chandpur (চাঁদপুর)", "Lakshmipur (লক্ষ্মীপুর)",
            "Rangamati (রাঙ্গামাটি)", "Khagrachhari (খাগড়াছড়ি)", "Bandarban (বান্দরবান)"
        ],
        "Rajshahi (রাজশাহী)": [
            "Rajshahi (রাজশাহী)", "Bogra (বগুড়া)", "Pabna (পাবনা)", "Sirajganj (সিরাজগঞ্জ)", 
            "Natore (নাটোর)", "Naogaon (নওগাঁ)", "Chapainawabganj (চাঁপাইনবাবগঞ্জ)", "Joypurhat (জয়পুরহাট)"
        ],
        "Khulna (খুলনা)": [
            "Khulna (খুলনা)", "Jessore (যশোর)", "Kushtia (কুষ্টিয়া)", "Magura (মাগুরা)", 
            "Narail (নড়াইল)", "Bagerhat (বাগেরহাট)", "Satkhira (ساتক্ষীরা)", "Jhenaidah (ঝিনাইদহ)", 
            "Chuadanga (চুয়াডাঙ্গা)", "Meherpur (মেহেরপুর)"
        ],
        "Barishal (বরিশাল)": [
            "Barishal (বরিশাল)", "Patuakhali (পটুয়াখালী)", "Bhola (ভোলা)", "Pirojpur (পিরোজপুর)", 
            "Barguna (বরগুনা)", "Jhalokati (ঝালকাঠি)"
        ],
        "Sylhet (সিলেট)": [
            "Sylhet (সিলেট)", "Moulvibazar (মৌলভীবাজার)", "Habiganj (হবিগঞ্জ)", "Sunamganj (সুনামগঞ্জ)"
        ],
        "Rangpur (রংপুর)": [
            "Rangpur (রংপুর)", "Dinajpur (দিনাজপুর)", "Gaibandha (গাইবান্ধা)", "Kurigram (কুড়িগ্রাম)", 
            "Nilphamari (নীলফামারী)", "Lalmonirhat (লালমনিরহাট)", "Panchagarh (পঞ্চগড়)", "Thakurgaon (ঠাকুরগাঁও)"
        ],
        "Mymensingh (ময়মনসিংহ)": [
            "Mymensingh (ময়মনসিংহ)", "Jamalpur (জামালপুর)", "Netrokona (নেত্রকোনা)", "Sherpur (শেরপুর)"
        ]
    }

geo_data = load_bangladesh_complete_geo()

# --- 2. SQLite Database Setup ---
DB_NAME = "voter_database.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS voters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            division TEXT,
            district TEXT,
            area_type TEXT,
            sub_district TEXT,
            union_or_ward TEXT,
            ward_no TEXT,
            name TEXT,
            father_name TEXT,
            nid TEXT UNIQUE,
            raw_text TEXT
        )
    ''')
    conn.commit()
    conn.close()

def insert_voters(voter_data_list):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    for voter in voter_data_list:
        try:
            cursor.execute('''
                INSERT OR IGNORE INTO voters (division, district, area_type, sub_district, union_or_ward, ward_no, name, father_name, nid, raw_text)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (voter['division'], voter['district'], voter['area_type'], voter['sub_district'], voter['union_or_ward'], voter['ward_no'], voter['name'], voter['father_name'], voter['nid'], voter['raw_text']))
        except Exception:
            pass
    conn.commit()
    conn.close()

init_db()

# --- 3. JPype & Apache PDFBox Setup (JClass Server Friendly) ---
jar_path = "pdfbox-app-3.0.7.jar" 
if not jpype.isJVMStarted():
    try:
        jpype.startJVM(convertStrings=True, classpath=[jar_path])
    except Exception as e:
        st.error(f"JVM Start korte problem hoyeche: {e}")

ByteArrayInputStream = jpype.JClass("java.io.ByteArrayInputStream")
PDDocument = jpype.JClass("org.apache.pdfbox.pdmodel.PDDocument")
PDFTextStripper = jpype.JClass("org.apache.pdfbox.text.PDFTextStripper")
Loader = jpype.JClass("org.apache.pdfbox.loader.Loader")

def check_and_decode(raw_text):
    if re.search(r'[\u0980-\u09FF]', raw_text):
        return raw_text
    bijoy_map = {'w': 'ি', 'v': 'া', 'b': 'ন', 'g': '।', 'A': 'আ', 'g': 'গ', 'h': 'ব', 'j': 'ক', 'l': 'ত', 'm': 'ম', 'n': 'ন', 'p': 'প', 'r': 'র', 's': 'স', 't': 'ত', 'u': 'ু', 'z': 'য'}
    return "".join([bijoy_map.get(char, char) for char in raw_text])

# --- 4. Streamlit UI ---
st.set_page_config(layout="wide", page_title="Dynamic Voter Finder Pro")
st.title("Dynamic Voter Finder (64 Districts Complete)")
st.write("---")

# --- 5. Sidebar: Dynamic Chain Selection ---
st.sidebar.header("1. Area Selection & PDF Upload")

divisions = list(geo_data.keys())
selected_division = st.sidebar.selectbox("বিভাগ সিলেক্ট করুন (Division)", divisions)

districts = geo_data.get(selected_division, [])
selected_district = st.sidebar.selectbox("জেলা সিলেক্ট করুন (District)", districts)

selected_type = st.sidebar.selectbox("এলাকার ধরন (Area Type)", ["উপজেলা (Upazila)", "সিটি কর্পোরেশন (City Corp)", "পৌরসভা (Pourashava)", "ক্যান্টনমেন্ট (Cantonment)"])

# Complete accurate field entry (Ekta data o jeno miss na jay)
selected_sub_dist = st.sidebar.text_input(f"{selected_type} এর নাম লিখুন", placeholder="উদা: উখিয়া / উত্তর সিটি")
selected_union_or_ward = st.sidebar.text_input("ইউনিয়ন / ওয়ার্ড / ইউনিটের নাম লিখুন", placeholder="উদা: রাজাপালং / ওয়ার্ড নং ১")
selected_ward_no = st.sidebar.text_input("গ্রাম / পাড়া / অতিরিক্ত তথ্য (ঐচ্ছিক)", placeholder="উদা: গ্রাম- ১নং ওয়ার্ড")

uploaded_file = st.sidebar.file_uploader("ভোটার তালিকার PDF আপলোড করুন", type=["pdf"])

if uploaded_file is not None:
    if st.sidebar.button("PDF প্রসেস এবং ডাটাবেজে সেভ করুন"):
        if not selected_sub_dist or not selected_union_or_ward:
            st.sidebar.error("⚠️ দয়া করে উপজেলার নাম এবং ইউনিয়ন/ওয়ার্ডের নাম ইনপুট দিন!")
        else:
            with st.spinner('PDFBox er madhome data extract hocche...'):
                try:
                    pdf_bytes = uploaded_file.read()
                    java_bytes_stream = ByteArrayInputStream(pdf_bytes)
                    
                    doc = Loader.loadPDF(java_bytes_stream)
                    stripper = PDFTextStripper()
                    
                    temp_voter_list = []
                    
                    for page_num in range(1, doc.getNumberOfPages() + 1):
                        stripper.setStartPage(page_num)
                        stripper.setEndPage(page_num)
                        page_text = stripper.getText(doc)
                        
                        decoded_text = check_and_decode(page_text)
                        names = re.findall(r'নাম:\s*(.*)', decoded_text)
                        fathers = re.findall(r'পিতা:\s*(.*)', decoded_text)
                        nids = re.findall(r'জাতীয় পরিচয়পত্র নং:\s*(\d+)', decoded_text)
                        
                        for i in range(len(names)):
                            temp_voter_list.append({
                                "division": selected_division,
                                "district": selected_district,
                                "area_type": selected_type,
                                "sub_district": selected_sub_dist.strip(),
                                "union_or_ward": selected_union_or_ward.strip(),
                                "ward_no": selected_ward_no.strip() if selected_ward_no else "N/A",
                                "name": names[i].strip(),
                                "father_name": fathers[i].strip() if i < len(fathers) else "N/A",
                                "nid": nids[i].strip() if i < len(nids) else "N/A",
                                "raw_text": decoded_text
                            })
                    
                    doc.close()
                    
                    if temp_voter_list:
                        insert_voters(temp_voter_list)
                        st.sidebar.success(f"সফলভাবে {len(temp_voter_list)} টি রেকর্ড ডাটাবেজে স্টোর হয়েছে!")
                    else:
                        st.sidebar.warning("কোনো ভোটার ডাটা খুঁজে পাওয়া যায়নি।")
                except Exception as e:
                    st.sidebar.error(f"Error: {str(e)}")

# --- 6. Main Dashboard Panel ---
st.header("2. ভোটার অনুসন্ধান প্যানেল")

col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("ফিল্টার এবং সার্চ ফলাফল")
    
    f_col1, f_col2, f_col3 = st.columns(3)
    with f_col1:
        filter_div = st.selectbox("বিভাগ ফিল্টার", ["সব বিভাগ"] + divisions)
    with f_col2:
        available_districts = geo_data.get(filter_div, []) if filter_div != "সব বিভাগ" else []
        filter_dist = st.selectbox("জেলা ফিল্টার", ["সব জেলা"] + available_districts)
    with f_col3:
        search_query = st.text_input("নাম বা এনআইডি দিয়ে লাইভ সার্চ করুন")

    query = "SELECT id, division, district, area_type, sub_district, union_or_ward, name, father_name, nid FROM voters WHERE 1=1"
    params = []
    
    if filter_div != "সব বিভাগ":
        query += " AND division = ?"
        params.append(filter_div)
    if filter_dist and filter_dist != "সব জেলা":
        query += " AND district = ?"
        params.append(filter_dist)
    if search_query:
        query += " AND (name LIKE ? OR nid LIKE ?)"
        params.append(f"%{search_query}%")
        params.append(f"%{search_query}%")
        
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    
    if not df.empty:
        st.write(f"মোট রেকর্ড পাওয়া গেছে: {len(df)} টি")
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("ডাটাবেজে কোনো রেকর্ড পাওয়া যায়নি।")

with col2:
    st.subheader("বিস্তারিত প্রোফাইল")
    if not df.empty:
        selected_id = st.selectbox("বিস্তারিত দেখতে আইডি (ID) সিলেক্ট করুন:", df['id'].tolist())
        
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT name, father_name, nid, division, district, area_type, sub_district, union_or_ward, ward_no FROM voters WHERE id = ?", (selected_id,))
        voter_detail = cursor.fetchone()
        conn.close()
        
        if voter_detail:
            v_name = st.text_input("ভোটারের নাম", voter_detail[0])
            v_father = st.text_input("পিতা/স্বামীর নাম", voter_detail[1])
            v_nid = st.text_input("এনআইডি নম্বর", voter_detail[2])
            
            full_addr = f"বিভাগ: {voter_detail[3]}, জেলা: {voter_detail[4]}, ধরণ: {voter_detail[5]}, এলাকা: {voter_detail[6]}, ইউনিয়ন/ওয়ার্ড: {voter_detail[7]}, পাড়া/গ্রাম/ওয়ার্ড: {voter_detail[8]}"
            st.text_area("প্রশাসনিক ঠিকানা", full_addr)
            
            st.code(f"নাম: {v_name}\nপিতা: {v_father}\nNID: {v_nid}\nঠিকানা: {full_addr}", language="text")
