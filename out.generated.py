import matplotlib.pyplot as plt
import pandas as pd

def plot(data: pd.DataFrame):
    filtered_data = data[data['HasAmmunitionSupplyCap'] == True][['ForceIdentifier']]
    force_identifier_counts = filtered_data['ForceIdentifier'].value_counts().reset_index()
    force_identifier_counts.columns = ['ForceIdentifier', 'Count']
    
    plt.figure(figsize=(10, 6))
    ax = force_identifier_counts.plot.pie(y='Count', autopct='%1.1f%%', startangle=90)
    ax.set_title('Trace un pie chart des EntityIdentifier qui ont des HasAmmunitionSupplyCap')
    plt.legend(title="ForceIdentifier", loc="center left", bbox_to_anchor=(1, 0, 0.5, 1))
    return plt;

chart = plot(data)