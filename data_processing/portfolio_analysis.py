import pandas as pd
import plotly.graph_objects as go

def load_portfolio_data(file_path):
    return pd.read_csv(file_path)

def create_portfolio_graph(df):
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(x=df['Date'], y=df['CumulativeROI'], mode='lines', name='Nancy Pelosi ROI'))
    fig.add_trace(go.Scatter(x=df['Date'], y=df['CopyCumulativeROI'], mode='lines', name='Copy Trade ROI'))
    fig.add_trace(go.Scatter(x=df['Date'], y=df['SPYCumROI'], mode='lines', name='SPY ROI'))
    
    fig.update_layout(
        title='Nancy Pelosi Portfolio ROI Comparison',
        xaxis_title='Date',
        yaxis_title='Cumulative ROI',
        legend_title='ROI Type',
        hovermode='x unified'
    )
    
    return fig

def preview_graph(file_path):
    df = load_portfolio_data(file_path)
    fig = create_portfolio_graph(df)
    fig.show()

# Uncomment the following line to preview the graph
preview_graph('data_processing/portfolio_roi.csv')