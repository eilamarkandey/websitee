import pandas as pd
from datetime import datetime
import xlsxwriter
import win32com.client
import os
import time
import networkx as nx
import plotly.graph_objects as go
import plotly.express as px
import textwrap
import dash
from dash import html, dcc
from dash.dependencies import Input, Output
import dash_bootstrap_components as dbc
import json  # Add this at the top with other imports
import traceback
import re

 ## FINE
# Define file paths
input_path = r"C:\Users\eilam\OneDrive\CEC\ECA Campaigns_FY25_ALL_v2.xlsx"
output_path = r"C:\Users\eilam\OneDrive\CEC\ECA Campaigns_FY25_BINARY.xlsx"

# Define Stata's epoch
STATA_EPOCH = pd.Timestamp('1960-01-01')

# Load data
df = pd.read_excel(input_path)

# Convert column names to lowercase and fix spaces
df.columns = df.columns.str.lower().str.replace(' ', '')

# Split date and time columns
df['startdate'] = df['startdateandtime'].str.split(',').str[0]
df['enddate'] = df['enddateandtime'].str.split(',').str[0]
df['starttime'] = df['startdateandtime'].str.split(',').str[1]
df['endtime'] = df['enddateandtime'].str.split(',').str[1]

# Drop original date and time columns
df.drop(columns=['startdateandtime', 'enddateandtime'], inplace=True)

# Convert date columns to datetime and then to Stata format (days since 1960-01-01)
df['num_startdate'] = pd.to_datetime(df['startdate'], format='%m/%d/%Y', errors='coerce')
df['num_startdate'] = (df['num_startdate'] - STATA_EPOCH).dt.days

# Create a unique Parent Campaign ID
df['parents_id'] = df['parentcampaignname'].astype('category').cat.codes

# Sort and generate campaign sequence numbers
df.sort_values(by=['parentcampaignname', 'num_startdate'], inplace=True)
df['num_campaigns'] = df.groupby('parentcampaignname').cumcount() + 1

# Create binary columns for activity types
df['meeting'] = (df['ecaactivitytype'] == 'Meeting').astype(int)
df['event'] = (df['ecaactivitytype'] == 'Event').astype(int)

# Create binary columns for interaction types
df['firsttime'] = ((df['interactiontype'] == "1st Time Inquiry – Requested by Org or Group") | 
                   (df['interactiontype'] == "1st Time Outreach – Initiated by ECA Staff")).astype(int)
df['frst_inquiry'] = (df['interactiontype'] == "1st Time Inquiry – Requested by Org or Group").astype(int)
df['frst_outreach'] = (df['interactiontype'] == "1st Time Outreach – Initiated by ECA Staff").astype(int)
df['followup_mtg'] = (df['interactiontype'] == "Follow Up Project Planning or Problem-Solving Meeting").astype(int)
df['reoccurring'] = (df['interactiontype'] == "Reoccurring activity").astype(int)
df['repeat'] = (df['interactiontype'] == "Repeat – For Purposes of Ongoing Participation or to Rep ECA").astype(int)
df['community_mtg'] = (df['interactiontype'] == "Community Meeting").astype(int)
df['standalone'] = (df['interactiontype'] == "Stand alone activity").astype(int)
df['scheduling'] = (df['interactiontype'] == "Scheduling or Show-and-Tell Visit").astype(int)
df['concerns'] = (df['interactiontype'] == "Resident, Institutional or City Concern").astype(int)
df['other'] = (df['interactiontype'] == "Other, such as Room Request").astype(int)

# Read the members file
members_path = r"C:\Users\eilam\OneDrive\CEC\ECA Campaign Members_FY25_ALL.xlsx"
members_df = pd.read_excel(members_path)

# Filter members file for first-time interactions
members_filtered = members_df[
    (members_df['Interaction Type'] == "1st Time Inquiry – Requested by Org or Group") | 
    (members_df['Interaction Type'] == "1st Time Outreach – Initiated by ECA Staff")
]
members_filtered.to_excel(r"C:\Users\eilam\OneDrive\CEC\ECA Campaign Members_FY25_members_filtered.xlsx", index=False)

# Get unique parent campaigns with first-time interactions
unique_parent_campaigns = members_filtered['Parent Campaign: Campaign Name'].unique()

# Filter the original dataframe to include only interactions for these parent campaigns
df_filtered = df[df['parentcampaignname'].isin(unique_parent_campaigns)]

# Create binary columns for each interaction type for summing purposes
interaction_types = df['interactiontype'].dropna().unique()
for interaction in interaction_types:
    df_filtered.loc[:, interaction.lower().replace(' ', '_').replace('–', '').replace('(', '').replace(')', '')] = (df_filtered['interactiontype'] == interaction).astype(int)

# Create a total column for the number of interactions each parent campaign has
df_filtered['total_interactions'] = df_filtered.groupby('parentcampaignname')['interactiontype'].transform('count')

# Calculate days from first-time interaction
# Find the first interaction date for each campaign
first_interactions = df_filtered[
    (df_filtered['interactiontype'] == "1st Time Inquiry – Requested by Org or Group") | 
    (df_filtered['interactiontype'] == "1st Time Outreach – Initiated by ECA Staff")
].groupby('parentcampaignname')['num_startdate'].min()

# Calculate days from first interaction
df_filtered['days_from_first'] = df_filtered.apply(
    lambda row: row['num_startdate'] - first_interactions[row['parentcampaignname']], 
    axis=1
)

# Mark any additional first-time interactions after day 0 as invalid
mask = (df_filtered['days_from_first'] > 0) & (
    (df_filtered['interactiontype'] == "1st Time Inquiry – Requested by Org or Group") |
    (df_filtered['interactiontype'] == "1st Time Outreach – Initiated by ECA Staff")
)
df_filtered.loc[mask, 'days_from_first'] = None  # Set to None to exclude from graph

# Save the filtered dataframe to a new Excel file
df_filtered.to_excel(r"C:\Users\eilam\OneDrive\CEC\ECA Campaigns_FY25_filtered_interactions.xlsx", index=False)

# Save the binary data
try:
    df.to_excel(output_path, index=False)
except PermissionError:
    print("Please close any Excel applications that might be using the file and try again.")
    exit()

# Filter v2 file for first-time interactions
v2_path = r"C:\Users\eilam\OneDrive\CEC\ECA Campaigns_FY25_ALL_v2.xlsx"
v2_df = pd.read_excel(v2_path)
filtered_first_time = v2_df[
    (v2_df['Interaction Type'] == "1st Time Inquiry – Requested by Org or Group") | 
    (v2_df['Interaction Type'] == "1st Time Outreach – Initiated by ECA Staff")
]
filtered_first_time.to_excel(r"C:\Users\eilam\OneDrive\CEC\ECA Campaigns_FY25_filtered_first_time.xlsx", index=False)

# Print summary once at the end
print("\nFiles created:")
print(f"1. Binary indicators file")
print(f"   - Saved to: {output_path}")
print(f"   - Contains all interactions with binary columns")

print(f"\n2. Filtered first-time interactions from v2 file")
print(f"   - Contains {len(filtered_first_time)} interactions")
print(f"   - Saved to: ECA Campaigns_FY25_filtered_first_time.xlsx")

print(f"\n3. Filtered first-time interactions from members file")
print(f"   - Contains {len(members_filtered)} interactions")
print(f"   - Saved to: ECA Campaign Members_FY25_members_filtered.xlsx")

print(f"\n4. Filtered interactions for parent campaigns with first-time interactions")
print(f"   - Contains {len(df_filtered)} interactions")
print(f"   - Saved to: ECA Campaigns_FY25_filtered_interactions.xlsx")

# Calculate statistics from correct sources
v2_first_time_total = len(filtered_first_time)  # From v2 file
unique_eca = members_filtered[members_filtered['ECA Affiliation Name'].notna()]['ECA Affiliation Name'].nunique()  # From members file
unique_campaigns = len(unique_parent_campaigns)  # Unique parent campaigns with first-time interactions

# Initialize Dash app
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])

def create_campaign_boxes():
    """Create clickable boxes for each campaign"""
    campaign_boxes = []
    
    for campaign in sorted(members_filtered['Parent Campaign: Campaign Name'].unique()):
        campaign_data = members_filtered[members_filtered['Parent Campaign: Campaign Name'] == campaign]
        
        box = dbc.Col(
            dbc.Card([
                dbc.CardBody([
                    html.H5(campaign, className="card-title"),
                    html.P(f"People involved: {len(campaign_data)}", className="card-text"),
                    dbc.Button("View Details", 
                             id={'type': 'campaign-button', 'index': campaign},
                             color="primary")
                ])
            ], className="h-100 shadow-sm"),
            width=4,
            className="mb-4"
        )
        campaign_boxes.append(box)
    
    return campaign_boxes

# Create layout
app.layout = html.Div([
    # Header
    html.Div([
        html.H1("ECA Engagement Dashboard", className="display-4 text-center mb-4"),
        html.H4("First-Time Interactions Analysis", className="text-center text-muted mb-5")
    ], className="container mt-4"),

    # Main stats row with correct data sources
    dbc.Row([
        dbc.Col([
            html.Div([
                html.H2(f"{v2_first_time_total}", className="display-3 text-primary"),
                html.P("Total First-Time Interactions", className="lead")
            ], className="text-center p-4 border rounded")
        ], width=4),
        dbc.Col([
            html.Div([
                html.H2(f"{unique_eca}", className="display-3 text-success"),
                html.P("Unique ECA Affiliations", className="lead")
            ], className="text-center p-4 border rounded")
        ], width=4),
        dbc.Col([
            html.Div([
                html.H2(f"{unique_campaigns}", className="display-3 text-info"),
                html.P("Parent Campaigns", className="lead")
            ], className="text-center p-4 border rounded")
        ], width=4),
    ], className="mb-5"),

    # Campaign boxes
    dbc.Row(
        create_campaign_boxes(),
        className="mb-4"
    ),

    # Dropdown for site filter
    html.Div([
        dcc.Dropdown(
            id='site-filter',
            options=[{'label': site, 'value': site} for site in df['site'].unique()],
            placeholder="Select a site"
        )
    ], className="mb-4"),

    # Time graph
    dcc.Graph(id='time-graph'),

    # Modal for campaign details
    dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle("Campaign Details")),
        dbc.ModalBody(id="campaign-details-body"),
        dbc.ModalFooter(
            dbc.Button("Close", id="close-modal", className="ms-auto")
        )
    ], id="campaign-modal", size="lg"),

    # Footer
    html.Footer([
        html.P("Data source: ECA Campaign Members FY25", className="text-muted text-center")
    ], className="mt-5")

], className="container-fluid px-4 py-4")

# Callback for modal
@app.callback(
    [Output("campaign-modal", "is_open"),
     Output("campaign-details-body", "children")],
    [Input({"type": "campaign-button", "index": dash.ALL}, "n_clicks"),
     Input('time-graph', 'clickData'),
     Input("close-modal", "n_clicks")],
    prevent_initial_call=True
)
def toggle_modal(campaign_clicks, click_data, close_clicks):
    ctx = dash.callback_context
    if not ctx.triggered:
        return False, ""
    
    trigger_id = ctx.triggered[0]["prop_id"]
    
    try:
        # Handle close button
        if "close-modal" in trigger_id:
            return False, ""
            
        # Get campaign name
        if "campaign-button" in trigger_id:
            button_id = json.loads(trigger_id.split('.')[0])
            campaign_name = button_id['index']
        elif "time-graph.clickData" in trigger_id:
            campaign_name = click_data['points'][0]['customdata'][0]
            days_after = click_data['points'][0]['customdata'][1]
        else:
            return False, ""

        # Get campaign data
        campaign_data = members_df[
            members_df['Parent Campaign: Campaign Name'] == campaign_name
        ]

        if campaign_data.empty:
            return True, html.Div("No data available for this campaign")

        # Create modal content with additional info for graph clicks
        details = html.Div([
            html.H4(campaign_name, className="mb-4"),
            html.Div([
                html.Div([
                    html.H5(f"Campaign: {sub_campaign}", className="mt-4 mb-3"),
                    html.H6("ECA Affiliations and Participants:", className="mb-2"),
                    html.Ul([
                        html.Li([
                            html.Strong(f"{eca}: "),
                            ", ".join(sorted(set(names)))
                        ])
                        for eca, names in campaign_data[
                            campaign_data['Campaign Name'] == sub_campaign
                        ].groupby('ECA Affiliation Name')['Full Name'].apply(list).items()
                        if pd.notna(eca)
                    ])
                ])
                for sub_campaign in sorted(campaign_data['Campaign Name'].unique())
            ]),
            # Add days info if clicked from graph
            html.Div(
                f"Days after first interaction: {days_after}" if 'days_after' in locals() else "",
                className="mt-3 text-muted"
            )
        ])
        
        return True, details

    except Exception as e:
        print(f"Error in toggle_modal: {str(e)}")
        return False, html.Div("An error occurred while loading campaign details")

@app.callback(
    Output('time-graph', 'figure'),
    Input('site-filter', 'value')
)
def update_time_graph(selected_site):
    try:
        filtered_df = df_filtered[df_filtered['site'] == selected_site] if selected_site else df_filtered
        
        if filtered_df.empty:
            return go.Figure()

        # Define ordered list of interaction types
        ordered_types = [
            "1st Time Inquiry – Requested by Org or Group",    # Must be first
            "1st Time Outreach – Initiated by ECA Staff",      # Must be second
            "Follow Up Project Planning or Problem-Solving Meeting",
            "Reoccurring activity",
            "Repeat – For Purposes of Ongoing Participation or to Rep ECA",
            "Community Meeting",
            "Stand alone activity",
            "Scheduling or Show-and-Tell Visit",
            "Resident, Institutional or City Concern",
            "Other, such as Room Request"
        ]

        # Define corresponding colors
        color_map = {
            ordered_types[0]: "#1f77b4",  # First Time Inquiry - Blue
            ordered_types[1]: "#2ca02c",  # First Time Outreach - Green
            ordered_types[2]: "#FF0000",  # Red
            ordered_types[3]: "#00FF00",  # Green
            ordered_types[4]: "#0000FF",  # Blue
            ordered_types[5]: "#FFA500",  # Orange
            ordered_types[6]: "#800080",  # Purple
            ordered_types[7]: "#008080",  # Teal
            ordered_types[8]: "#FF69B4",  # Pink
            ordered_types[9]: "#808080"   # Gray
        }

        fig = go.Figure()
        legend_items = []  # Use list instead of set to maintain order

        # First, add all traces in the correct order
        for interaction_type in ordered_types:
            # Check if this interaction type exists in the filtered data
            type_data = filtered_df[filtered_df['interactiontype'] == interaction_type]
            if not type_data.empty:
                for parent_campaign in filtered_df['parentcampaignname'].unique():
                    campaign_data = type_data[type_data['parentcampaignname'] == parent_campaign]
                    
                    # Add gray bar if this is the first interaction type
                    if interaction_type == ordered_types[0]:
                        max_days = filtered_df[filtered_df['parentcampaignname'] == parent_campaign]['days_from_first'].max()
                        fig.add_trace(go.Bar(
                            name=parent_campaign,
                            y=[parent_campaign],
                            x=[max_days],
                            marker_color='lightgray',
                            width=0.5,
                            orientation='h',
                            showlegend=False
                        ))

                    # Add markers for this interaction type
                    for _, row in campaign_data.iterrows():
                        # Skip first-time interactions that aren't at day 0
                        if ("1st Time" in interaction_type and row['days_from_first'] != 0):
                            continue
                        
                        fig.add_trace(go.Scatter(
                            y=[parent_campaign],
                            x=[row['days_from_first']],
                            mode='markers',
                            marker=dict(
                                color=color_map[interaction_type],
                                size=10,
                                symbol='line-ns',
                                line=dict(width=3, color=color_map[interaction_type])
                            ),
                            name=interaction_type,
                            showlegend=(interaction_type not in legend_items),
                            customdata=[[parent_campaign, int(row['days_from_first']), interaction_type]],
                            hovertemplate=(
                                f"Campaign: {parent_campaign}<br>"
                                f"Interaction Type: {interaction_type}<br>"
                                f"Days after first interaction: {int(row['days_from_first'])}<br>"
                                f"Click for details<extra></extra>"
                            )
                        ))
                        if interaction_type not in legend_items:
                            legend_items.append(interaction_type)

        # Update layout with legend configuration
        fig.update_layout(
            title="Campaign Timeline by Parent Campaign",
            yaxis_title="Parent Campaign",
            xaxis_title="Days Since First Interaction",
            xaxis=dict(
                range=[0, filtered_df['days_from_first'].max() * 1.1],
                tickmode="array",
                tickvals=list(range(0, int(filtered_df['days_from_first'].max()) + 30, 30)),
                gridcolor='lightgray',
                griddash='dot',
                showgrid=True
            ),
            showlegend=True,
            legend_title="Interaction Types",
            template="plotly_white",
            height=600,
            barmode='overlay',
            legend=dict(
                yanchor="top",
                y=0.99,
                xanchor="left",
                x=1.02,
                traceorder='normal'  # Use normal trace order as we're adding traces in the desired order
            )
        )

        return fig

    except Exception as e:
        print(f"Error in update_time_graph: {str(e)}")
        traceback.print_exc()
        return go.Figure()

# Add after loading the data files (after members_df = pd.read_excel(members_path))

def clean_parent_campaign(name):
    """Remove all prefix variations and get only the campaign name"""
    if isinstance(name, str):
        # Remove everything before and including the first occurrence of " - "
        if " - " in name:
            name = name.split(" - ", 1)[1].strip()
        
        # Remove any remaining "CEC - " or similar prefixes
        prefixes = [
            "PARENT1: CEC",
            "PARENT 1: CEC",
            "PARENT1:",
            "PARENT 1:",
            "CEC"
        ]
        
        for prefix in prefixes:
            if name.startswith(prefix):
                name = name[len(prefix):].strip()
        
        # Remove any leading or trailing dashes or em dashes
        name = re.sub(r'^[\-\–]+', '', name).strip()
        
        return name.strip()
    return name

# Clean campaign names in all dataframes before any filtering or processing
df['parentcampaignname'] = df['parentcampaignname'].apply(clean_parent_campaign)
df_filtered['parentcampaignname'] = df_filtered['parentcampaignname'].apply(clean_parent_campaign)
members_df['Parent Campaign: Campaign Name'] = members_df['Parent Campaign: Campaign Name'].apply(clean_parent_campaign)
members_filtered['Parent Campaign: Campaign Name'] = members_filtered['Parent Campaign: Campaign Name'].apply(clean_parent_campaign)

# Verify the cleaning worked
print("\nVerifying cleaned campaign names:")
print("First 5 campaign names:")
for name in df['parentcampaignname'].unique()[:5]:
    print(f"- {name}")

# Run the app
if __name__ == '__main__':
    print("\nDash is running on http://127.0.0.1:8050/")
    app.run_server(debug=True)

print("\nDashboard is running!")
print(f"Total First-Time Interactions (from v2): {v2_first_time_total}")
print(f"Unique ECA Affiliations (from members): {unique_eca}")
print(f"Unique Parent Campaigns (from members): {unique_campaigns}")
print("- Access the dashboard at http://127.0.0.1:8050/")
print("- Click on campaign boxes to see details")



