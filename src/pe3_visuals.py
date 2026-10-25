"""Visuales reutilizables para la narrativa de los notebooks PE3."""
import math
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

PALETTE = {
    "ink": "#18324b",
    "blue": "#4b78a8",
    "green": "#6b8f71",
    "orange": "#c45a46",
    "muted": "#657786",
    "edge": "#d8e2ec",
    "paper": "#f3f6f9",
}

def kpi_cards(items, title="Indicadores clave", note=None, ncols=4):
    """Render compact, notebook-safe KPI cards.

    items: sequence of (label, value, detail). Values are preformatted strings so
    units and denominators stay explicit in each notebook's analytical context.
    """
    items = list(items)
    if not items:
        return None
    ncols = max(1, min(int(ncols), len(items)))
    nrows = math.ceil(len(items) / ncols)
    fig, axes = plt.subplots(nrows, ncols, figsize=(4.0*ncols, 1.9*nrows), squeeze=False)
    fig.patch.set_facecolor(PALETTE["paper"])
    for ax in axes.flat:
        ax.set_axis_off()
    for ax, item in zip(axes.flat, items):
        label, value, detail = item
        ax.set_xlim(0, 1); ax.set_ylim(0, 1)
        card = FancyBboxPatch((.035,.08),.93,.84,boxstyle="round,pad=0.02,rounding_size=0.04",
                              facecolor="white",edgecolor=PALETTE["edge"],linewidth=1.2)
        ax.add_patch(card)
        ax.add_patch(FancyBboxPatch((.035,.08),.035,.84,boxstyle="round,pad=0.01,rounding_size=0.03",
                                    facecolor=PALETTE["blue"],edgecolor=PALETTE["blue"],linewidth=0))
        ax.text(.12,.76,str(label),fontsize=10,color=PALETTE["muted"],weight="normal",
                ha="left",va="center",wrap=True)
        ax.text(.12,.47,str(value),fontsize=19,color=PALETTE["ink"],weight="bold",
                ha="left",va="center",wrap=True)
        ax.text(.12,.20,str(detail),fontsize=8.5,color=PALETTE["muted"],
                ha="left",va="center",wrap=True)
    fig.suptitle(title,fontsize=14,weight="bold",color=PALETTE["ink"],x=.04,ha="left",y=1.01)
    if note:
        fig.text(.04,.005,str(note),fontsize=8.5,color=PALETTE["muted"],ha="left",va="bottom",wrap=True)
    plt.tight_layout(rect=(0,.05,1,.94))
    plt.show()
    return fig
