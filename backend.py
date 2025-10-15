from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
import pandas as pd
from datetime import datetime
import shutil
import os
from pydantic import BaseModel
from fastapi import BackgroundTasks
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig


class StockUpdate(BaseModel):
    medicine_id: int
    quantity_consumed: int
class OrderRequest(BaseModel):
    vendor_email: str


DB_FILE = 'medicine_shop.db'

app = FastAPI()

# Allow CORS for local development (adjust origin in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Process Excel file to update stock
@app.post("/upload_excel/")
async def upload_excel(file: UploadFile = File(...)):
    if not file.filename.endswith('.xlsx'):
        raise HTTPException(status_code=400, detail="Only .xlsx files are allowed")
    
    temp_file = f"temp_{file.filename}"
    with open(temp_file, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    df = pd.read_excel(temp_file)

    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()

        for _, row in df.iterrows():
            name = row['medicine_name']
            qty = int(row['quantity_received'])

            cursor.execute('SELECT id, current_stock FROM Medicine WHERE name = ?', (name,))
            result = cursor.fetchone()

            if result:
                medicine_id = result[0]
                current_stock = result[1]
                new_stock = current_stock + qty
                cursor.execute('UPDATE Medicine SET current_stock = ? WHERE id = ?', (new_stock, medicine_id))
            else:
                cursor.execute('INSERT INTO Medicine (name, current_stock, reorder_threshold, desired_stock_level) VALUES (?, ?, 30, 150)', (name, qty))
    
        conn.commit()

    os.remove(temp_file)
    return {"message": "Excel processed and stock updated"}

# Get all medicines
@app.get("/medicines/")
def get_medicines():
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT name, SUM(current_stock) as total_stock
            FROM Medicine
            GROUP BY name
        ''')
        medicines = cursor.fetchall()
    return [{"name": name, "current_stock": total_stock} for name, total_stock in medicines]


# Update stock based on consumption
@app.post("/update_stock/")
def update_stock(update: StockUpdate):
    medicine_id = update.medicine_id
    quantity_consumed = update.quantity_consumed
    date = datetime.now().strftime('%Y-%m-%d')

    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        
        # Insert into ConsumptionHistory
        cursor.execute('INSERT INTO ConsumptionHistory (medicine_id, quantity_consumed, date) VALUES (?, ?, ?)',
                       (medicine_id, quantity_consumed, date))

        # Update stock
        cursor.execute('UPDATE Medicine SET current_stock = current_stock - ? WHERE id = ?', (quantity_consumed, medicine_id))

        # Check reorder
        cursor.execute('SELECT current_stock, reorder_threshold, desired_stock_level FROM Medicine WHERE id = ?', (medicine_id,))
        current_stock, reorder_threshold, desired_stock_level = cursor.fetchone()

        if current_stock <= reorder_threshold:
            suggested_qty = desired_stock_level - current_stock
            cursor.execute('''
            INSERT INTO UpcomingOrderList (medicine_id, suggested_quantity, reason, date_added)
            VALUES (?, ?, ?, ?)
            ''', (medicine_id, suggested_qty, "Stock below threshold", date))
        
        conn.commit()

    return {"message": "Stock updated"}


# Get upcoming orders
@app.get("/upcoming_orders/")
def get_upcoming_orders():
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT Medicine.name, SUM(UpcomingOrderList.suggested_quantity) as total_qty, MAX(UpcomingOrderList.date_added) as last_date
            FROM UpcomingOrderList
            JOIN Medicine ON UpcomingOrderList.medicine_id = Medicine.id
            GROUP BY Medicine.name
            ORDER BY last_date DESC
        ''')
        orders = cursor.fetchall()

    return [{
        "medicine_name": name,
        "suggested_quantity": qty,
        "date_added": last_date
    } for name, qty, last_date in orders]


# --- Mail Configuration ---
conf = ConnectionConfig(
    MAIL_USERNAME = "horcrux1619@gmail.com",
    MAIL_PASSWORD = "edjy agjl gktn ailm",
    MAIL_FROM = "horcrux1619@gmail.com",
    MAIL_PORT=587,
    MAIL_SERVER="smtp.gmail.com",
    MAIL_FROM_NAME="Medicine Order System",
    USE_CREDENTIALS=True,
    MAIL_STARTTLS=True,      # Required now
    MAIL_SSL_TLS=False 
)

@app.get("/generate_order/")
def generate_order():
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT Medicine.id, Medicine.name, SUM(UpcomingOrderList.suggested_quantity) as total_qty
            FROM UpcomingOrderList
            JOIN Medicine ON UpcomingOrderList.medicine_id = Medicine.id
            GROUP BY Medicine.id, Medicine.name
        ''')
        orders = cursor.fetchall()

    order_list = [{"medicine_id": mid, "name": name, "quantity": qty} for mid, name, qty in orders]
    return {"orders": order_list}


@app.post("/send_order/")
async def send_order(order_request: OrderRequest, background_tasks: BackgroundTasks):
    vendor_email = order_request.vendor_email
    
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT Medicine.name, SUM(UpcomingOrderList.suggested_quantity) as total_qty
            FROM UpcomingOrderList
            JOIN Medicine ON UpcomingOrderList.medicine_id = Medicine.id
            GROUP BY Medicine.id, Medicine.name
        ''')
        orders = cursor.fetchall()

    if not orders:
        return {"message": "No orders to send"}

    # Create Excel file
    df = pd.DataFrame(orders, columns=["Medicine", "Quantity"])
    file_name = "new_order.xlsx"
    df.to_excel(file_name, index=False)

    # Prepare email
    message = MessageSchema(
    subject="New Order Request",
    recipients=[vendor_email],
    body="Please find attached the new order list.",
    subtype="plain",  # This tells FastMail the email is plain text
    attachments=[file_name]
)


    fm = FastMail(conf)
    background_tasks.add_task(fm.send_message, message)

    return {"message": "Order email sent"}
