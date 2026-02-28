import os
import json
import time
import sqlite3
from dotenv import load_dotenv
from pageindex import PageIndexClient

load_dotenv()

PAGEINDEX_API_KEY = os.getenv("PAGEINDEX_API_KEY")
pi_client = PageIndexClient(api_key=PAGEINDEX_API_KEY)

DB_PATH = os.path.join(os.path.dirname(__file__), "docs.db")



def initialize_database():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_name TEXT,
                doc_id TEXT UNIQUE,
                status TEXT,
                tree_structure TEXT
            )
        """)
        conn.commit()


def save_tree_structure(doc_id: str, tree_data):
    try:
        tree_json = json.dumps(tree_data)

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE users 
                SET tree_structure = ?, status = ?
                WHERE doc_id = ?
                """,
                (tree_json, "completed", doc_id),
            )
            conn.commit()

        print("Tree structure saved successfully ✅")

    except Exception as e:
        print("Error saving tree:", str(e))


def save_status(doc_id: str, status: str):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET status = ? WHERE doc_id = ?",
                (status, doc_id),
            )
            conn.commit()
    except Exception as e:
        print("Error saving status:", str(e))


def submit_document(file_path: str):
    try:
        result = pi_client.submit_document(file_path=file_path)
        doc_id = result.get("doc_id")

        if not doc_id:
            return {"status": "error", "error": "No doc_id returned"}

        file_name = os.path.basename(file_path)

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO users (file_name, doc_id, status)
                VALUES (?, ?, ?)
                """,
                (file_name, doc_id, "processing"),
            )
            conn.commit()

        print(f"Document submitted: {file_name}")
        print(f"Doc ID: {doc_id}")

        return {"status": "success", "doc_id": doc_id}

    except Exception as e:
        return {"status": "error", "error": str(e)}


def wait_for_completion_and_save(doc_id: str, interval=5, timeout=300):
    start_time = time.time()

    while True:
        try:
            tree_response = pi_client.get_tree(doc_id)
            status = tree_response.get("status")

            print("Current tree status:", status)

            if status == "completed":
                tree_data = tree_response.get("result")

                if not tree_data:
                    print("No result data found ❌")
                    return

                save_tree_structure(doc_id, tree_data)
                return

            if status == "failed":
                print("Processing failed ❌")
                save_status(doc_id, "failed")
                return

            if time.time() - start_time > timeout:
                print("Timeout reached ⏳")
                return

            time.sleep(interval)

        except Exception as e:
            print("Error during polling:", str(e))
            return


def get_tree_from_db(doc_id: str):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT tree_structure FROM users WHERE doc_id = ?",
            (doc_id,),
        )
        row = cursor.fetchone()

        if row and row[0]:
            return json.loads(row[0])
        return None


if __name__ == "__main__":

    initialize_database()

    file_path = r"C:\Users\amanm\Desktop\learning\pageindex-exp\RLM.pdf"

    # Submit document
    result = submit_document(file_path)

    if result["status"] != "success":
        print("Submission failed:", result["error"])
        exit()

    doc_id = result["doc_id"]

    # Wait for processing + Save tree JSON
    wait_for_completion_and_save(doc_id)

    # Verify saved data 
    saved_tree = get_tree_from_db(doc_id)
    if saved_tree:
        print("Saved tree preview:")
        print(json.dumps(saved_tree[:1], indent=2))