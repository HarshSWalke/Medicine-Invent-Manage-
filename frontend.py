import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime

DB_FILE = 'medicine_shop.db'

# --- Page Configuration ---
st.set_page_config(page_title="Medical Store Manager", layout="wide", initial_sidebar_state="expanded")

# --- Section 1: Header and Upload Box ---
st.markdown("<h1 style='text-align: center;'>📋 Upload Medicines Excel Sheet</h1>", unsafe_allow_html=True)

uploaded_file = st.file_uploader(
    label="Upload your Excel file here (.xlsx)",
    type=['xlsx'],
    help="Excel should contain columns: medicine_name, quantity_received",
)

if uploaded_file:
    st.success("File uploaded successfully")

# --- Section 2: Styling and Layout ---
st.markdown(
    """
    <style>
    .upload-box {
        background-color: #FF4C4C;
        color: black;
        padding: 20px;
        margin-top: 30px;
        margin-bottom: 30px;
        text-align: center;
        border-radius: 10px;
        height: 30vh;
    }
    .medicine-grid {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        grid-template-rows: repeat(2, auto);
        grid-gap: 20px;
        margin-top: 20px;
    }
    .medicine-box {
        background-color: #6a5acd;  /* Nice blue shade */
        color: white;
        padding: 15px;
        border-radius: 10px;
        min-height: 150px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
    }
    .medicine-name {
        font-weight: bold;
        font-size: 18px;
        text-align: center;
        margin-bottom: 10px;
    }
    .sold-input {
        width: 80%;
    }
    </style>
    """,
    unsafe_allow_html=True
)

if uploaded_file:
    # Styled Upload Box Info
    st.markdown('<div class="upload-box">Upload Excel file with columns:<br><strong>medicine_name, quantity_received</strong></div>', unsafe_allow_html=True)

    # Display Medicine Grid
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT id, name, current_stock FROM Medicine')
    medicines = cursor.fetchall()
    conn.close()

    st.markdown('<div class="medicine-grid">', unsafe_allow_html=True)

    for med in medicines:
        med_id, med_name, med_stock = med
        st.markdown('<div class="medicine-box">', unsafe_allow_html=True)
        st.markdown(f'<div class="medicine-name">{med_name} (Stock: {med_stock})</div>', unsafe_allow_html=True)
        sold_units = st.number_input(f'Sold units (ID: {med_id})', min_value=0, key=f'sold_{med_id}')
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)

    # Update Database on Submit
    if st.button("Update Sales"):
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        for med in medicines:
            med_id, med_name, med_stock = med
            sold_units = st.session_state.get(f'sold_{med_id}', 0)
            if sold_units > 0:
                cursor.execute('UPDATE Medicine SET current_stock = current_stock - ? WHERE id = ?', (sold_units, med_id))
                cursor.execute('''INSERT INTO ConsumptionHistory (medicine_id, quantity_consumed, date) VALUES (?, ?, ?)''',
                               (med_id, sold_units, datetime.now().strftime('%Y-%m-%d')))
        conn.commit()
        conn.close()
        st.success("Sales data updated successfully!")
