import sqlite3
import uuid
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "agents.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS agents") # Reset for new schema
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS agents (
            id TEXT PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            display_name TEXT NOT NULL,
            description TEXT,
            personality TEXT,
            steps TEXT,
            avatar TEXT,
            suggestions TEXT
        )
    """)
    
    initial_agents = [
        (
            "agent-sm-stable-id", 
            "agent_sm", 
            "Callie (Strategic Marketing)", 
            "Specializes in marketing reports, sales analysis, and strategic data insights.",
            "Analytical, professional, and results-oriented. Focused on growth and ROI. Directly answer questions or write reports without using introductory phrases like 'As a specialist' or 'As a manager'.",
            "Data Extraction -> Compliance Audit -> Strategic Critique -> Executive Report",
            "/callie-avatar-sm.png",
            "Generate a quarterly sales report;Audit my latest CRM campaign;Analyze marketing ROI for last month"
        ),
        (
            "agent-cs-stable-id", 
            "agent_cs", 
            "Callie (Client Services)", 
            "Focused on client relationship management, service delivery metrics, and satisfaction analysis.",
            "Attentive, professional, and proactive. Prioritizes client success and high-quality service delivery. Directly answer questions or write reports without using introductory phrases like 'As a specialist' or 'As a manager'.",
            "Account Health Check -> Success Planning -> Service Optimization",
            "/callie-avatar-cs.png",
            "Perform an account health check;Draft a client success plan;Analyze service delivery metrics"
        ),
        (
            "agent-admin-stable-id", 
            "agent_admin", 
            "Callie (Administrative)", 
            "Handles internal administrative tasks, scheduling logic, and resource management.",
            "Precise, organized, and reliable. Values efficiency and structural integrity. Directly answer questions or write reports without using introductory phrases like 'As a specialist' or 'As a manager'.",
            "Resource Auditing -> Schedule Optimization -> Logistics Planning",
            "/callie-avatar-admin.png",
            "Audit internal resource usage;Optimize my team's schedule;Create a logistics planning draft"
        )
    ]
    cursor.executemany("INSERT INTO agents (id, name, display_name, description, personality, steps, avatar, suggestions) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", initial_agents)
    conn.commit()
    conn.close()

def get_agents():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM agents")
    agents = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return agents

if __name__ == "__main__":
    init_db()
    print("Database initialized and populated.")
