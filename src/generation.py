from pageindex import PageIndexClient
import pageindex.utils as utils
from dotenv import load_dotenv
import os
import sqlite3
import json
import asyncio
import openai

load_dotenv()

DB_PATH = os.path.join(os.path.dirname(__file__), "docs.db")
PAGEINDEX_API_KEY = os.getenv("PAGEINDEX_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

_pi_client = PageIndexClient(api_key=PAGEINDEX_API_KEY)


def load_tree_from_db(file_name: str):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT tree_structure FROM users WHERE file_name = ?",
            (file_name,),
        )
        row = cursor.fetchone()

    if not row or not row[0]:
        print("Tree structure not found.")
        return None

    return json.loads(row[0])


async def call_llm(prompt, model="stepfun/step-3.5-flash:free", temperature=0):
    client = openai.AsyncOpenAI(
        api_key=OPENROUTER_API_KEY,
        base_url="https://openrouter.ai/api/v1",
    )

    response = await client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
    )

    return response.choices[0].message.content.strip()


async def ask(query: str, tree: dict, node_map: dict) -> str:

    tree_without_text = utils.remove_fields(
        json.loads(json.dumps(tree)),
        fields=["text"]
    )

    # Step 1: Find relevant nodes
    search_prompt = f"""
You are given a question and a tree structure of a document.
Each node contains a node id, node title, and a corresponding summary.
Your task is to find all nodes that are likely to contain the answer to the question.

Question: {query}

Document tree structure:
{json.dumps(tree_without_text, indent=2)}

Please reply in the following JSON format:
{{
    "thinking": "<Your reasoning>",
    "node_list": ["node_id_1", "node_id_2"]
}}
Return ONLY valid JSON.
"""

    tree_search_result = await call_llm(search_prompt)

    try:
        tree_search_result_json = json.loads(tree_search_result)
    except json.JSONDecodeError:
        print("\n[Error] Could not parse LLM search result.")
        print(tree_search_result)
        return "Sorry, I couldn't process that query."

    print("\nReasoning:")
    utils.print_wrapped(tree_search_result_json.get("thinking", ""))

    node_list = tree_search_result_json.get("node_list", [])

    print("\nRetrieved Nodes:")
    for node_id in node_list:
        node = node_map.get(node_id)
        if node:
            page = node.get(
                "page_index",
                f"{node.get('start_index', '?')}-{node.get('end_index', '?')}"
            )
            print(f"  Node ID: {node['node_id']} | Page: {page} | Title: {node['title']}")

    relevant_content = "\n\n".join(
        node_map[nid]["text"]
        for nid in node_list
        if nid in node_map and "text" in node_map[nid]
    )

    if not relevant_content:
        return "No relevant sections found in the document."

    print("\nContext Preview:")
    utils.print_wrapped(relevant_content[:1000] + "...")

    # Step 2: Generate answer
    answer_prompt = f"""
Answer the question based ONLY on the context below.

Question: {query}

Context: {relevant_content}

Provide a clear and concise answer.
"""

    answer = await call_llm(answer_prompt)
    return answer



#chat loop

async def main():
    print("\nAvailable Documents:\n")

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT file_name, status FROM users")
        files = cursor.fetchall()

    if not files:
        print("No documents found in database.")
        return

    completed_files = [f for f in files if f[1] == "completed"]

    if not completed_files:
        print("No completed documents available.")
        return

    for i, (file_name, status) in enumerate(completed_files, 1):
        print(f"{i}. {file_name}  (status: {status})")

    try:
        choice_index = int(input("\nSelect document number: ")) - 1
        selected_file = completed_files[choice_index][0]
    except (ValueError, IndexError):
        print("Invalid selection.")
        return

    tree = load_tree_from_db(selected_file)
    if not tree:
        return

    print(f"\nLoaded document: {selected_file}")

    node_map = utils.create_node_mapping(tree)

    print("\n" + "=" * 20)
    print("  PageIndex Document Chatbot")
    print("  Type 'exit' to quit.")
    print("=" * 20)

    while True:
        print()
        query = input("You: ").strip()

        if not query:
            continue

        if query.lower() == "exit":
            print("Goodbye!")
            break

        answer = await ask(query, tree, node_map)
        print(f"\nBot: {answer}")


# run
if __name__ == "__main__":
    asyncio.run(main())