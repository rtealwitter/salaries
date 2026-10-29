"""Publication figures from combined_long.csv; deterministic PNG and SVG exports."""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, MaxNLocator
from adjustText import adjust_text
ROOT=Path(__file__).resolve().parents[1]
FIG=ROOT/'figures';FIG.mkdir(exist_ok=True)
RED='#a52b45';BLUE='#246b88';GRAY='#b7c1c8';INK='#23313d'
FOCUS=['Claremont McKenna College','Harvey Mudd College','Pomona College','Williams College','Amherst College','Swarthmore College']
NAMES={'Claremont McKenna College':'CMC','Washington and Lee University':'Washington & Lee','College of the Holy Cross':'Holy Cross','University of Richmond':'Richmond'}
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,'axes.spines.right':False,'axes.labelcolor':INK,'text.color':INK,'axes.edgecolor':'#d2d9dd','xtick.color':INK,'ytick.color':INK,'axes.titleweight':'bold','svg.fonttype':'none','savefig.facecolor':'white','figure.facecolor':'white','axes.facecolor':'white','svg.hashsalt':'faculty-salaries-v1'})

def name(s):return NAMES.get(s,s.replace(' College','').replace(' University',''))
def color(s):return RED if s=='Claremont McKenna College' else BLUE if s in FOCUS else GRAY

def finish(fig,stem,caption):
    fig.text(.02,.016,caption,fontsize=9,color='#596976',va='bottom')
    for ext in ['png']:fig.savefig(FIG/f'{stem}.{ext}',dpi=240,bbox_inches='tight',metadata={'Creator':'Faculty salaries reproducible pipeline',**({'Date':None} if ext=='svg' else {})})
    plt.close(fig)

def style_money(ax):
    ax.yaxis.set_major_formatter(FuncFormatter(lambda x,p:f'${x/1000:,.0f}k'));ax.grid(axis='y',color='#edf0f2');ax.set_axisbelow(True)

def scatter(d,rank,year,adjusted,ylim):
    col='salary_cost_adjusted' if adjusted else 'salary_nominal';prefix='adjusted' if adjusted else 'nominal';label='Regional purchasing power' if adjusted else 'Nominal salary'
    fig,ax=plt.subplots(figsize=(13.5,9.5));fig.subplots_adjust(left=.09,right=.98,bottom=.16,top=.88)
    ax.scatter(d.usnews_rank_2027,d[col],s=[90 if n in FOCUS else 45 for n in d.college],c=[color(n) for n in d.college],edgecolor='white',linewidth=.8,zorder=3)
    ax.set(xlim=(-1,35),ylim=ylim,xlabel='U.S. News National Liberal Arts Colleges rank, 2027 (ties preserved)',ylabel=f'{label} · annual dollars per faculty member')
    style_money(ax);ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    texts=[ax.text(r.usnews_rank_2027,r[col],name(r.college),fontsize=10,color=RED if r.college==FOCUS[0] else INK,weight='bold' if r.college in FOCUS else 'normal') for _,r in d.dropna(subset=[col]).iterrows()]
    np.random.seed(42);adjust_text(texts,ax=ax,expand=(1.12,1.3),force_text=(.5,.7),iter_lim=700,arrowprops=dict(arrowstyle='-',color='#a9b2ba',lw=.65))
    fig.suptitle(f'{label} and college rank',x=.09,ha='left',fontsize=22,weight='bold');ax.set_title(f'{rank.title()} professors · academic year {year}–{str(year+1)[-2:]} · 30 civilian colleges',loc='left',fontsize=13,pad=16,fontweight='normal')
    finish(fig,f'{prefix}_salary_vs_rank'+('' if rank=='assistant' else '_'+rank),f'Sources: NCES IPEDS; U.S. News 2027 ranks via College Kickstart'+(f'; BEA {year} all-items RPP.' if adjusted else '.')+'\nFull-time instructional staff; nine-month-equivalent average salaries. Red: Claremont McKenna (CMC).')

def bars(d,rank,year,adjusted):
    col='salary_cost_adjusted' if adjusted else 'salary_nominal';prefix='adjusted' if adjusted else 'nominal';title='Purchasing-power ranking' if adjusted else 'Nominal salary ranking'
    d=d.sort_values(col,ascending=True);fig,ax=plt.subplots(figsize=(12,12));fig.subplots_adjust(left=.25,right=.91,top=.9,bottom=.12)
    y=np.arange(len(d));ax.barh(y,d[col],color=[color(n) for n in d.college],height=.72)
    ax.set_yticks(y,[name(n) for n in d.college]);ax.set_xlim(0,d[col].max()*1.14);ax.xaxis.set_major_formatter(FuncFormatter(lambda x,p:f'${x/1000:,.0f}k'));ax.grid(axis='x',color='#edf0f2');ax.set_axisbelow(True)
    for j,(_,r) in enumerate(d.iterrows()):
        if pd.notna(r[col]):ax.text(r[col]+900,j,f'${r[col]:,.0f}',va='center',fontsize=10)
        else:ax.text(500,j,'Missing',va='center')
    ax.set_xlabel('Annual salary'+(f' ÷ ({year} all-items RPP / 100)' if adjusted else ' · current dollars'))
    fig.suptitle(title,x=.03,y=.97,ha='left',fontsize=23,weight='bold');fig.text(.03,.935,f'{rank.title()} professors · {year}–{str(year+1)[-2:]} · fixed 2027 cohort',fontsize=13)
    finish(fig,f'{prefix}_salary_ranking'+('' if rank=='assistant' else '_'+rank),f'Sources: NCES IPEDS {year}–{str(year+1)[-2:]}; '+(f'BEA {year} RPP; ' if adjusted else '')+'U.S. News 2027 cohort via College Kickstart.\nFull-time instructional staff; nine-month-equivalent averages. Red: CMC.')

def slopes(d,rank,year):
    fig,ax=plt.subplots(figsize=(14,13));fig.subplots_adjust(left=.30,right=.70,top=.88,bottom=.10)
    for _,r in d.iterrows():
        a,b=r.salary_nominal_rank,r.salary_cost_adjusted_rank
        if pd.isna(a+b):continue
        col=color(r.college);ax.plot([0,1],[a,b],color=col,lw=2.6 if r.college==FOCUS[0] else 1.3,alpha=1 if r.college in FOCUS else .7)
        ax.scatter([0,1],[a,b],color=col,s=22,zorder=3)
        ax.text(-.04,a,f'{name(r.college)}  {int(a):2}',ha='right',va='center',fontsize=10,color=RED if r.college==FOCUS[0] else INK)
        ax.text(1.04,b,f'{int(b):2}  {name(r.college)}',ha='left',va='center',fontsize=10,color=RED if r.college==FOCUS[0] else INK)
    ax.set_ylim(31,0);ax.set_xlim(-.02,1.02);ax.set_xticks([0,1],['Nominal salary rank','Cost-adjusted salary rank']);ax.xaxis.tick_top();ax.set_yticks([])
    for spine in ax.spines.values():spine.set_visible(False)
    fig.suptitle('How regional prices change the salary ranking',x=.03,ha='left',fontsize=22,weight='bold');fig.text(.03,.935,f'{rank.title()} professors · {year}–{str(year+1)[-2:]} salaries / {year} prices',fontsize=13)
    finish(fig,'salary_rank_changes'+('' if rank=='assistant' else '_'+rank),f'Sources: NCES IPEDS; BEA all-items RPP; fixed U.S. News 2027 cohort via College Kickstart.\nRanks within the 30-college cohort; 1 = highest. Red: CMC. Nonmetro colleges use their state’s nonmetro RPP.')

def trends(d,rank):
    fig,axes=plt.subplots(1,2,figsize=(16,7.5),sharey=True);fig.subplots_adjust(left=.07,right=.97,bottom=.20,top=.80,wspace=.14)
    for ax,col,title in zip(axes,['salary_nominal','salary_real_2024'],['Nominal dollars','2024 dollars · national PCE inflation adjustment']):
        for n,g in d.groupby('college'):
            if n==FOCUS[0]:continue
            g=g.set_index('year').reindex(range(d.year.min(),d.year.max()+1))
            ax.plot(g.index,g[col],color=GRAY,alpha=.7,lw=1)
            # Isolated early survey years are retained as dots, not interpolated.
            ax.scatter(g.index,g[col],s=4,color=GRAY,alpha=.5)
        g=d[d.college==FOCUS[0]].set_index('year').reindex(range(d.year.min(),d.year.max()+1))
        ax.plot(g.index,g[col],color=RED,lw=2.8,label='CMC',zorder=5);ax.scatter(g.index,g[col],s=16,color=RED,zorder=5)
        for year in [2012,2016]:ax.axvline(year,color='#7e8a93',ls=':',lw=1)
        ax.set_title(title,loc='left',fontsize=13);ax.set_xlabel('Academic year beginning in');style_money(ax)
    axes[0].set_ylabel('Average annual salary');axes[0].plot([],[],c=GRAY,label='Other 29 colleges');axes[0].legend(frameon=False,loc='upper left')
    fig.suptitle(f'{rank.title()} professor salaries over time',x=.07,ha='left',fontsize=23,weight='bold');fig.text(.07,.87,'Claremont McKenna highlighted against a fixed cohort of 30 civilian liberal arts colleges',fontsize=13)
    finish(fig,'salary_trends'+('' if rank=='assistant' else '_'+rank),'Sources: NCES IPEDS/HEGIS (early years via Urban Institute); BEA PCE via FRED. Salary averages, not starting salaries.\nDotted lines: conversion-method changes in 2012 and 2016. Early contract populations vary; see README. Gaps are not interpolated.')

def spread(d,rank):
    recent=d[d.year>=2008];q=recent.groupby('year').salary_real_cost_adjusted_2024.quantile([.1,.5,.9]).unstack()
    fig,ax=plt.subplots(figsize=(12,7));fig.subplots_adjust(left=.1,bottom=.19,top=.84)
    ax.fill_between(q.index,q[.1],q[.9],color='#dbe8ee',label='10th–90th percentile across colleges');ax.plot(q.index,q[.5],color=BLUE,label='Cohort median',lw=2)
    g=recent[recent.college==FOCUS[0]];ax.plot(g.year,g.salary_real_cost_adjusted_2024,color=RED,lw=2.5,label='CMC')
    ax.legend(frameon=False);ax.set_xlabel('Academic year beginning in');ax.set_ylabel('Annual salary in 2024 national purchasing-power dollars');style_money(ax)
    fig.suptitle(f'Purchasing-power differences over time · {rank} professors',x=.1,ha='left',fontsize=19,weight='bold')
    finish(fig,'salary_dispersion_'+rank,'Sources: NCES IPEDS; BEA RPP and PCE. Salary ÷ (RPP/100) × (PCE2024/PCEyear).\nUnweighted college distribution; composition changes when observations are missing. Vassar RPP unavailable before 2016.')

def main():
    d=pd.read_csv(ROOT/'data/processed/combined_long.csv');year=int(d[d.salary_cost_adjusted.notna()].year.max())
    for rank in ['assistant','associate','full']:
        h=d[d.academic_rank==rank];latest=h[h.year==year].copy()
        values=latest[['salary_nominal','salary_cost_adjusted']];lo=np.floor(values.min().min()/10000)*10000-7000;hi=np.ceil(values.max().max()/10000)*10000+7000
        for adj in [False,True]:scatter(latest,rank,year,adj,(lo,hi));bars(latest,rank,year,adj)
        slopes(latest,rank,year);trends(h,rank);spread(h,rank)
    print('Generated 21 figures, as PNG.')
if __name__=='__main__':main()
