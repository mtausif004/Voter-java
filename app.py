import streamlit as st
import pandas as pd
import jpype
import jpype.imports
import sqlite3
import re

# --- ১. ডাটাবেজ সেটআপ (SQLite) ---
DB_NAME = "voter_database.db"

def init_db():
    """ডাটাবেজ এবং টেবিল তৈরি করার ফাংশন"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS voters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            district TEXT,
            upazila TEXT,
            name TEXT,
            father_name TEXT,
            nid TEXT UNIQUE,
            raw_text TEXT
        )
    ''')
    conn.commit()
    conn.close()

def insert_voters(voter_data_list):
    """ডাটাবেজে ভোটারদের তথ্য ইনসার্ট করার ফাংশন"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    for voter in voter_data_list:
        try:
            # UNIQUE NID হলে ডুপ্লিকেট এড়াতে INSERT OR IGNORE ব্যবহার করা হয়েছে
            cursor.execute('''
                INSERT OR IGNORE INTO voters (district, upazila, name, father_name, nid, raw_text)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (voter['district'], voter['upazila'], voter['name'], voter['father_name'], voter['nid'], voter['raw_text']))
        except Exception as e:
            pass
    conn.commit()
    conn.close()

# ডাটাবেজ ইনিশিয়ালাইজ করা
init_db()

# --- ২. JPype ও PDFBox সেটআপ ---
# জার ফাইলের নাম আপনার ডাউনলোড করা ৩.০.৭ ভার্সনের সাথে মিলিয়ে দেওয়া হলো
jar_path = "pdfbox-app-3.0.7.jar" 

if not jpype.isJVMStarted():
    try:
        jpype.startJVM(convertStrings=True, classpath=[jar_path])
    except Exception as e:
        st.error(f"JVM স্টার্ট করতে সমস্যা হয়েছে: {e}")

# জাভা ক্লাসগুলো সঠিকভাবে ইম্পোর্ট করা (সংশোধিত)
from java.io import ByteArrayInputStream
from org.apache.pdfbox.pdmodel import PDDocument
from org.apache.pdfbox.text import PDFTextStripper

# --- ৩. বায়ান্নো (SutonnyMJ) ডিকোডার লজিক ---
def check_and_decode(raw_text):
    """টেক্সট Nikosh (Unicode) নাকি SutonnyMJ তা চেক করে ডিকোড করার ফাংশন"""
    if re.search(r'[\u0980-\u09FF]', raw_text):
        return raw_text # সরাসরি ইউনিকোড হলে রিটার্ন করবে
    
    # SutonnyMJ এর জন্য একটি বেসিক ক্যারেক্টার ম্যাপ (প্রয়োজন অনুযায়ী বড় করতে হবে)
    bijoy_map = {'w': 'ি', 'v': 'া', 'b': 'ন', 'g': '।', 'A': 'আ', 'g': 'গ', 'h': 'ব', 'j': 'ক', 'l': 'ত', 'm': 'ম', 'n': 'ন', 'p': 'প', 'r': 'র', 's': 'স', 't': 'ত', 'u': 'ু', 'z': 'য'}
    converted = "".join([bijoy_map.get(char, char) for char in raw_text])
    return converted

# --- ৪. Streamlit UI ডিজাইন ---
st.set_page_config(layout="wide", page_title="Dynamic Voter Finder Pro")

st.title("Dynamic Voter Finder (SQLite Store & Search)")
st.write("---")

# সাইডবার: ডাটা ইনপুট ও ফাইল আপলোড প্যানেল
st.sidebar.header("১. ডেটা ইম্পোর্ট ও আপলোড")
selected_district = st.sidebar.selectbox("জেলা সিলেক্ট করুন", ["কক্সবাজার", "চট্টগ্রাম", "ঢাকা"])
selected_upazila = st.sidebar.selectbox("উপজেলা সিলেক্ট করুন", ["উখিয়া", "টেকনাফ", "চন্দнайш"])

uploaded_file = st.sidebar.file_uploader("ভোটার তালিকার PDF আপলোড করুন", type=["pdf"])

if uploaded_file is not None:
    if st.sidebar.button("PDF প্রসেস এবং ডাটাবেজে সেভ করুন"):
        with st.spinner('PDFBox এর মাধ্যমে ডাটা এক্সট্র্যাক্ট ও SQLite-এ সেভ হচ্ছে...'):
            try:
                pdf_bytes = uploaded_file.read()
                java_bytes_stream = ByteArrayInputStream(pdf_bytes)
                doc = PDDocument.load(java_bytes_stream)
                stripper = PDFTextStripper()
                
                temp_voter_list = []
                
                for page_num in range(1, doc.getNumberOfPages() + 1):
                    stripper.setStartPage(page_num)
                    stripper.setEndPage(page_num)
                    page_text = stripper.getText(doc)
                    
                    # টেক্সট ডিকোড করা
                    decoded_text = check_and_decode(page_text)
                    
                    # Regex দিয়ে ডেটা খোঁজা (পিডিএফ ফরম্যাট অনুযায়ী এটি বদলাতে পারে)
                    names = re.findall(r'নাম:\s*(.*)', decoded_text)
                    fathers = re.findall(r'পিতা:\s*(.*)', decoded_text)
                    nids = re.findall(r'জাতীয় পরিচয়পত্র নং:\s*(\d+)', decoded_text)
                    
                    for i in range(len(names)):
                        temp_voter_list.append({
                            "district": selected_district,
                            "upazila": selected_upazila,
                            "name": names[i].strip(),
                            "father_name": fathers[i].strip() if i < len(fathers) else "N/A",
                            "nid": nids[i].strip() if i < len(nids) else "N/A",
                            "raw_text": decoded_text
                        })
                
                doc.close()
                
                # ডাটাবেজে ডাটা পুশ করা
                if temp_voter_list:
                    insert_voters(temp_voter_list)
                    st.sidebar.success(f"সফলভাবে {len(temp_voter_list)} টি রেকর্ড ডাটাবেজে স্টোর হয়েছে!")
                else:
                    st.sidebar.warning("কোনো ভোটার ডাটা খুঁজে পাওয়া যায়নি। পিডিএফ ফরম্যাট চেক করুন।")
                    
            except Exception as e:
                st.sidebar.error(f"Error: {str(e)}")

# --- ৫. মূল স্ক্রিন: ডেটা সার্চ এবং ফাইন্ডアウト UI (ভিডিওর মতো ২ কলাম) ---
st.header("২. ডাটাবেজ অনুসন্ধান প্যানেল")

col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("ফিল্টার এবং সার্চ ফলাফল")
    
    # সার্চ ফিল্টার UI
    search_col1, search_col2, search_col3 = st.columns(3)
    with search_col1:
        filter_district = st.selectbox("জেলা ফিল্টার", ["সব জেলা", "কক্সবাজার", "চট্টগ্রাম", "ঢাকা"])
    with search_col2:
        filter_upazila = st.selectbox("উপজেলা ফিল্টার", ["সব উপজেলা", "উখিয়া", "টেকনাফ", "চন্দনাইশ"])
    with search_col3:
        search_query = st.text_input("নাম বা এনআইডি দিয়ে খুঁজুন (Live Search)")

    # SQL Query তৈরি করা ফিল্টারের ওপর ভিত্তি করে
    query = "SELECT id, district, upazila, name, father_name, nid FROM voters WHERE 1=1"
    params = []
    
    if filter_district != "সব জেলা":
        query += " AND district = ?"
        params.append(filter_district)
    if filter_upazila != "সব উপজেলা":
        query += " AND upazila = ?"
        params.append(filter_upazila)
    if search_query:
        query += " AND (name LIKE ? OR nid LIKE ?)"
        params.append(f"%{search_query}%")
        params.append(f"%{search_query}%")
        
    # ডাটাবেজ থেকে ডেটা রিড করে DataFrame এ নেওয়া
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    
    # গ্রিড ভিউতে দেখানো
    if not df.empty:
        st.write(f"মোট রেকর্ড পাওয়া গেছে: {len(df)} টি")
        
        # স্ট্রিমলিটের কাস্টম ডাটা এডিটর/টেবিল যা সিলেক্ট করা যায়
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("ডাটাবেজে কোনো রেকর্ড পাওয়া যায়নি অথবা ফিল্টারের সাথে মিলেনি।")

with col2:
    st.subheader("বিস্তারিত প্রোফাইল")
    if not df.empty:
        # ইউজার ডাটাবেজের কোন আইডিটি দেখতে চান তা সিলেক্ট করার অপশন
        selected_id = st.selectbox("বিস্তারিত দেখতে আইডি (ID) সিলেক্ট করুন:", df['id'].tolist())
        
        # নির্দিষ্ট আইডির ডাটা তুলে আনা
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT name, father_name, nid, district, upazila FROM voters WHERE id = ?", (selected_id,))
        voter_detail = cursor.fetchone()
        conn.close()
        
        if voter_detail:
            # টেক্সটবক্সে ডাটা শো করা
            v_name = st.text_input("ভোটারের নাম", voter_detail[0])
            v_father = st.text_input("পিতা/স্বামীর নাম", voter_detail[1])
            v_nid = st.text_input("এনআইডি নম্বর", voter_detail[2])
            v_address = st.text_area("ঠিকানা", f"{voter_detail[3]}, {voter_detail[4]}")
            
            # নোটপ্যাডে কপি করার জন্য কোড ব্লক জেনারেট করা
            copy_format = f"নাম: {v_name}\nপিতা: {v_father}\nNID: {v_nid}\nঠিকানা: {v_address}"
            st.code(copy_format, language="text")
