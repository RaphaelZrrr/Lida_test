import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

def plot(data: pd.DataFrame):
    data['EntityType'].value_counts().sort_index().plot(kind='bar')
    plt.title('Bar chart du nombre d\'entités par EntityType', wrap=True)
    plt.xlabel("Entity Type")
    plt.ylabel("Count")
    return plt

chart = plot(data)