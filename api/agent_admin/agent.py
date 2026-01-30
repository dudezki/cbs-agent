from google.adk.flows.llm_flows import instructions
from google.adk.agents.llm_agent import LlmAgent
from google.adk.agents.sequential_agent import SequentialAgent
from google.adk.agents.parallel_agent import ParallelAgent
from google.adk.tools.bigquery.bigquery_toolset import BigQueryToolset
from google.adk.tools.bigquery.config import BigQueryToolConfig
import os
from dotenv import load_dotenv

load_dotenv()

# Set credentials path if not already set in environment
if "GOOGLE_APPLICATION_CREDENTIALS" not in os.environ:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # credentials.json is likely in the 'api' folder (parent of 'agent_sm')
    creds_path = os.path.join(os.path.dirname(current_dir), "credentials.json")
    if os.path.exists(creds_path):
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = creds_path
        print(f"Loaded credentials from: {creds_path}")
    else:
        print(f"Warning: credentials.json not found at {creds_path}")

bq_config = BigQueryToolConfig(
    compute_project_id='callbox-core'
)
bq_toolset = BigQueryToolset(bigquery_tool_config=bq_config)

content_creator = LlmAgent(
    model='gemini-2.5-flash',
    name='writer',
    description='Senior Data Analyst & Drafter responsible for extracting data and writing the initial report.',
    instruction=(
        "You are a Senior Data Analyst and Report Drafter.\n"
        "Your goal is to create a detailed INITIAL DRAFT based on the user's request.\n"
        "CRITICAL DATA INSTRUCTIONS:\n"
        "- You have access to comprehensive business intelligence data.\n"
        "- Available data sources include:\n"
        "  1. Sales Performance Data (revenue, leads, pipeline metrics)\n"
        "  2. CRM Data (customer engagement, campaign activities, interaction logs)\n"
        "- QUERY the data first using the available tools. Do not hallucinate data.\n"
        "- When writing your report, refer to data sources using business-friendly names:\n"
        "  • Instead of technical schema names, use terms like 'Sales Performance Data', 'CRM Data', 'Campaign Activities and Engagement', etc.\n"
        "  • Avoid mentioning database schemas, table names, or technical identifiers in your final output.\n"
        "- Draft a comprehensive report including: Executive Summary, Key Findings, Data Analysis, and Initial Recommendations.\n"
        "Output the raw draft report. DO NOT use introductory phrases like 'As a Senior Data Analyst' or 'As a reporter'. Start directly with the content."
    ),
    tools=[bq_toolset],
)

auditor = LlmAgent(
    model='gemini-2.5-flash',
    name='auditor',
    description='Data Integrity & Compliance Auditor who verifies data usage and standards.',
    instruction=(
        "You are a Data Integrity and Compliance Auditor.\n"
        "Input: Draft report from the Content Creator.\n"
        "Task: AUDIT the draft for accuracy and compliance.\n"
        "- Verify that business data sources were properly utilized and cited.\n"
        "- Flag any vague claims that lack data backing (potential hallucinations).\n"
        "- Ensure the tone is professional, objective, and free of aggressive language.\n"
        "- Confirm that the report uses business-friendly terminology and avoids technical jargon (no schema/table names exposed).\n"
        "Output: The original draft text followed by your 'Audit Findings'. DO NOT use introductory phrases like 'As an auditor'. Respond directly."
    ),
)

critic = LlmAgent(
    model='gemini-2.5-flash',
    name='critic',
    description='Senior Strategic Analyst who critiques reports for depth, logic, and value.',
    instruction=(
        "You are a Senior Strategic Analyst known for your sharp critical thinking.\n"
        "Input: A draft report (potentially containing Audit Findings).\n"
        "Task: CRITIQUE the draft rigorously.\n"
        "- Check for data sufficiency: Did they use enough data? Is the interpretation correct?\n"
        "- Check for business value: Are the insights actionable? Is it just descriptive or prescriptive?\n"
        "- check for logic and flow.\n"
        "Output: A concise list of specific critiques and improvements needed. Do NOT rewrite the report yet. DO NOT use introductory phrases like 'As a critic'. Respond directly."
    ),
)

refiner = LlmAgent(
    model='gemini-2.5-flash',
    name='refiner',
    description='Lead Editor who finalizes the report into a high-value professional deliverable.',
    instruction=(
        "You are a Lead Editor and Communication Expert.\n"
        "Inputs: The Draft Report, Audit Findings, and Critic's Feedback.\n"
        "Task: REWRITE and POLISH the report into a final 'High-Value' Professional Deliverable.\n"
        "- Address all issues raised by the Auditor and Critic.\n"
        "- Use professional Markdown formatting (Headers, Bullet points, Bold text).\n"
        "- Ensure the tone is authoritative, clear, and executive-ready.\n"
        "- Structure: Title, Executive Summary, Strategic Analysis (incorporating data), detailed Findings, and Strategic Recommendations.\n"
        "- DO NOT use introductory phrases like 'As an editor' or 'As a professional'. Respond directly with the polished report."
    ),
)

title_agent = LlmAgent(
    model='gemini-2.5-flash',
    name='title_agent',
    description='Summarizes the initial conversation into a short title.',
    instruction=(
        "You are a Session Titling Specialist.\n"
        "Input: The first message of a user conversation.\n"
        "Task: Generate a VERY SHORT, succinct title (3-5 words max) that summarizes the user's intent.\n"
        "Examples:\n"
        "- 'Quarterly Sales Analysis'\n"
        "- 'CRM Data Audit'\n"
        "- 'Marketing Strategy Plan'\n"
        "Output: ONLY the title. No quotes, no preamble."
    ),
)


report_workflow = SequentialAgent(
    name='report_workflow',
    description='A multi-agent professional report workflow.',
    sub_agents=[content_creator, auditor, critic, refiner],
)

casual_agent = LlmAgent(
    model='gemini-2.5-flash',
    name='Callie_admin',
    description='A specialized Administrative assistant.',
    instruction=(
        "You are Callie, an Administrative Specialist assistant.\n"
        "Your focus is on organizational logistics, scheduling logic, and administrative efficiency.\n"
        "Engage in professional conversation and assist with administrative tasks.\n"
        "DO NOT use introductory phrases like 'As an Administrative Specialist'. Respond directly."
    ),
)

# The Manager is the Root Agent.
root_agent = LlmAgent(
    model='gemini-2.5-flash',
    name='manager_admin',
    description='Root agent for Administrative specialized tasks.',
    instruction=(
        "You are the Administrative Manager AI.\n"
        "Coordinate administrative requests and handle general queries via Callie_admin."
    ),
    sub_agents=[casual_agent]
)




