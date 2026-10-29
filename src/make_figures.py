"""Four consolidated figures. --legacy additionally recreates the original chart set."""
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
from matplotlib.patches import Rectangle
from adjustText import adjust_text
from make_legacy_figures import ROOT,FIG,RED,BLUE,GRAY,INK,FOCUS,name,finish,style_money
TITLES={'assistant':'Assistant professors','associate':'Associate professors','full':'Full professors'}
RANKS=list(TITLES)

def resolve_label_overlaps(ax,texts,targets):
    """Finish automatic layout with deterministic pixel-space separation and audit."""
    fig=ax.figure;fig.canvas.draw();renderer=fig.canvas.get_renderer()
    initial={id(t):ax.transData.transform(t.get_position())[1] for t in texts}
    for iteration in range(600):
        overlaps=0
        for j,a in enumerate(texts):
            for b in texts[j+1:]:
                aa=a.get_window_extent(renderer).expanded(1.035,1.12);bb=b.get_window_extent(renderer).expanded(1.035,1.12)
                if not aa.overlaps(bb):continue
                overlaps+=1
                lower,upper=(a,b) if initial[id(a)]<=initial[id(b)] else (b,a)
                lb=lower.get_window_extent(renderer).expanded(1.035,1.12);ub=upper.get_window_extent(renderer).expanded(1.035,1.12)
                shift=(lb.y1-ub.y0+1)/2
                for t,delta in [(lower,-shift),(upper,shift)]:
                    pos=ax.transData.transform(t.get_position());pos[1]+=delta
                    pos[1]=np.clip(pos[1],ax.bbox.y0+12,ax.bbox.y1-12)
                    t.set_position(ax.transData.inverted().transform(pos))
        if not overlaps:break
    remaining=sum(a.get_window_extent(renderer).overlaps(b.get_window_extent(renderer)) for j,a in enumerate(texts) for b in texts[j+1:])
    if remaining:raise ValueError(f'{remaining} unresolved text overlaps in {ax.get_title()}')
    for t,target in zip(texts,targets):
        distance=np.linalg.norm(ax.transData.transform(t.get_position())-ax.transData.transform(target))
        if distance>12:
            ax.annotate('',xy=target,xytext=t.get_position(),arrowprops=dict(arrowstyle='-',color='#9ba8b1',lw=.6),zorder=1)
    print(f'Label audit: {ax.get_title()}: {len(texts)} labels, {remaining} overlaps')

def comparison(d,year):
    latest=d[d.year==year];order=latest[latest.academic_rank=='assistant'].sort_values('salary_cost_adjusted',ascending=False).college.tolist()
    fig,axes=plt.subplots(1,3,figsize=(18,13),sharey=True);fig.subplots_adjust(left=.17,right=.98,bottom=.13,top=.85,wspace=.20)
    for ax,rank in zip(axes,RANKS):
        h=latest[latest.academic_rank==rank].set_index('college').reindex(order)
        for y,(n,r) in enumerate(h.iterrows()):
            col=RED if n==FOCUS[0] else BLUE
            if n==FOCUS[0]:ax.axhspan(y-.45,y+.45,color=RED,alpha=.06)
            ax.plot([r.salary_nominal,r.salary_cost_adjusted],[y,y],color=col,alpha=.7,lw=1.4)
            ax.scatter(r.salary_nominal,y,facecolor='white',edgecolor=col,s=40,zorder=3)
            ax.scatter(r.salary_cost_adjusted,y,color=col,s=40,zorder=3)
        ax.set_title(TITLES[rank],loc='left',fontsize=15,pad=32)
        r=h.loc[FOCUS[0]]
        ax.text(0,1.015,f'CMC salary rank: {r.salary_nominal_rank:.0f} → {r.salary_cost_adjusted_rank:.0f}',transform=ax.transAxes,color=RED,fontsize=10)
        ax.set_yticks(range(len(order)),[name(n) for n in order]);ax.set_ylim(len(order)-.4,-.7)
        ax.xaxis.set_major_formatter(FuncFormatter(lambda x,p:f'${x/1000:,.0f}k'));ax.grid(axis='x',color='#edf0f2');ax.set_axisbelow(True);ax.set_xlabel('Annual salary / purchasing power')
        lo=h[['salary_nominal','salary_cost_adjusted']].min().min();hi=h[['salary_nominal','salary_cost_adjusted']].max().max();ax.set_xlim(lo*.94,hi*1.05)
    for t,n in zip(axes[0].get_yticklabels(),order):
        if n==FOCUS[0]:t.set_color(RED);t.set_weight('bold')
    handles=[plt.Line2D([],[],marker='o',ls='',markerfacecolor='white',markeredgecolor=BLUE,label='Nominal salary'),plt.Line2D([],[],marker='o',ls='',color=BLUE,label='Cost-adjusted salary'),plt.Line2D([],[],color=RED,lw=2,label='CMC')]
    fig.legend(handles=handles,loc='upper left',bbox_to_anchor=(.17,.925),ncol=3,frameon=False)
    fig.suptitle('Which colleges pay best after accounting for regional prices?',x=.03,y=.98,ha='left',fontsize=23,weight='bold')
    fig.text(.03,.945,f'{year}–{str(year+1)[-2:]} salaries · {year} prices · one panel per academic rank',fontsize=13)
    finish(fig,'current_salary_comparison',f'Sources: NCES IPEDS; BEA {year} all-items RPP; fixed U.S. News 2027 civilian cohort via College Kickstart.\nNine-month-equivalent averages. Cost-adjusted salary = nominal salary ÷ (RPP/100). Rows sorted by assistant-professor purchasing power.\nNonmetro colleges use state nonmetro RPPs. Each panel has its own dollar scale; institutional averages are not starting salaries.')

def long_run(d):
    fig,axes=plt.subplots(2,3,figsize=(20,12));fig.subplots_adjust(left=.075,right=.98,bottom=.18,top=.88,hspace=.36,wspace=.20)
    for j,rank in enumerate(RANKS):
        h=d[d.academic_rank==rank]
        for i,col in enumerate(['salary_nominal','salary_real_cost_adjusted_2024']):
            years=range(int(d.year.min()) if i==0 else 2008,int(d.year.max())+1)
            ax=axes[i,j];q=h.groupby('year')[col].quantile([.1,.5,.9]).unstack().reindex(years)
            g=h[h.college==FOCUS[0]].set_index('year').reindex(years)
            ax.fill_between(q.index,q[.1],q[.9],color='#dce7ed');ax.plot(q.index,q[.5],color=BLUE,lw=1.6)
            line=g[col].copy();line.loc[2019]=np.nan
            ax.plot(g.index,line,color=RED,lw=2.3);ax.scatter(g.index,line,color=RED,s=14,zorder=3)
            ax.scatter([2019],[g.loc[2019,col]],facecolor='white',edgecolor=RED,s=45,zorder=4)
            if i==0:
                isolated=q.loc[[1980,1984,1985,1987]].dropna()
                ax.vlines(isolated.index,isolated[.1],isolated[.9],color='#b5c8d3',lw=3,zorder=0);ax.scatter(isolated.index,isolated[.5],color=BLUE,s=12)
            for year in [2012,2016]:ax.axvline(year,color='#8e9aa2',lw=.8,ls=':')
            style_money(ax);ax.set_title(TITLES[rank],loc='left',fontsize=15,pad=10);ax.set_xlabel('Academic year beginning in')
            ax.set_ylim(0,h[['salary_nominal','salary_real_cost_adjusted_2024']].max().max()*1.08)
            ax.set_ylabel('Nominal annual salary' if i==0 else 'Cost-adjusted salary · 2024 dollars')
            if i==1:ax.set_xticks([2008,2012,2016,2020,2024])
    fig.suptitle('CMC pay over time: nominal salary and regional purchasing power',x=.075,y=.99,ha='left',fontsize=24,weight='bold')
    handles=[plt.Line2D([],[],color=RED,lw=2.5,label='CMC'),plt.Line2D([],[],color=BLUE,lw=1.6,label='Cohort median'),Rectangle((0,0),1,1,color='#dce7ed',label='10th–90th percentile across colleges')]
    fig.legend(handles=handles,bbox_to_anchor=(.065,.965),loc='upper left',ncol=3,frameon=False)
    finish(fig,'historical_salary_trends','Sources: NCES IPEDS/HEGIS (1980–2002 via Urban Institute); BEA RPP; BEA PCE via FRED. Fixed 2027 cohort; unweighted college percentiles.\nTop: nominal dollars, 1980–2024. Bottom: salary ÷ (RPP/100) × PCE2024/PCEyear, 2008–2024. Time ranges differ because RPP starts in 2008.\nHollow CMC point in 2019: all ranks reported as 12-month contracts, unlike 2018/2020; do not read the dip as a verified pay cut.\nEarly contract populations vary. Dotted lines: 2012/2016 conversion changes. Missing years are not interpolated; see README.')

def relative_trends(d):
    h=d[d.year>=2008].copy();h['premium']=100*(h.salary_cost_adjusted/h.groupby(['academic_rank','year']).salary_cost_adjusted.transform('median')-1)
    latest=int(h.year.max());order=h[(h.year==latest)&h.academic_rank.eq('assistant')].sort_values('premium',ascending=False).college.tolist()
    years=sorted(h.year.unique());fig,axes=plt.subplots(1,3,figsize=(19,12),sharey=True);fig.subplots_adjust(left=.17,right=.94,bottom=.18,top=.87,wspace=.12)
    cmap=plt.get_cmap('RdBu_r').copy();cmap.set_bad('#e7e7e7')
    for ax,rank in zip(axes,RANKS):
        p=h[h.academic_rank==rank].pivot(index='college',columns='year',values='premium').reindex(index=order,columns=years)
        im=ax.imshow(p,aspect='auto',cmap=cmap,vmin=-30,vmax=30,interpolation='nearest')
        ax.set_title(TITLES[rank],loc='left',fontsize=15,pad=15)
        ticks=[k for k,y in enumerate(years) if y in [2008,2012,2016,2020,2024]];ax.set_xticks(ticks,[years[k] for k in ticks]);ax.set_yticks(range(len(order)),[name(n) for n in order]);ax.tick_params(axis='both',length=0,pad=8);ax.set_xlabel('Academic year beginning in')
        i=order.index(FOCUS[0]);ax.text(years.index(2019),i,'×',ha='center',va='center',fontsize=14,color='black')
        ax.add_patch(Rectangle((-.5,i-.5),len(years),1,fill=False,edgecolor=RED,lw=1.8))
        for spine in ax.spines.values():spine.set_visible(False)
    for t,n in zip(axes[0].get_yticklabels(),order):
        if n==FOCUS[0]:t.set_color(RED);t.set_weight('bold')
    cax=fig.add_axes([.36,.095,.4,.017]);cb=fig.colorbar(im,cax=cax,orientation='horizontal',extend='both');cb.set_label('Cost-adjusted salary relative to the cohort median (%)');cb.set_ticks([-30,-15,0,15,30])
    fig.suptitle('How each college’s purchasing-power position has changed',x=.03,y=.98,ha='left',fontsize=23,weight='bold')
    fig.text(.03,.937,'Red: above peer median   ·   Blue: below peer median   ·   Gray: unavailable   ·   CMC row outlined; × marks its 2019 contract-reporting break',fontsize=12)
    finish(fig,'relative_purchasing_power_trends','Sources: NCES IPEDS; BEA RPP. Premium = 100 × [(salary/RPP) ÷ median(salary/RPP) − 1], separately by year and academic rank.\nA relative comparison, not local inflation or individual pay growth. Vassar’s metro RPP is unavailable before 2016. Conversion changes in 2012 and 2016.\nRows follow the latest assistant-professor purchasing-power ranking. Rank-specific cohort medians use available observations; national inflation cancels in the ratio.')

def ranking_relationship(d,year):
    cols=['salary_nominal','salary_cost_adjusted']
    fig,axes=plt.subplots(2,3,figsize=(24,17));fig.subplots_adjust(left=.06,right=.98,bottom=.11,top=.90,hspace=.30,wspace=.18)
    for j,rank in enumerate(RANKS):
        h=d[d.year.eq(year)&d.academic_rank.eq(rank)]
        low=h[cols].min().min()-10000;high=h[cols].max().max()+12000
        for i,(col,title) in enumerate(zip(cols,['Nominal salary','Cost-adjusted salary'])):
            ax=axes[i,j]
            ax.scatter(h.usnews_rank_2027,h[col],c=[RED if n==FOCUS[0] else BLUE if n in FOCUS else GRAY for n in h.college],s=[70 if n in FOCUS else 35 for n in h.college],edgecolor='white',lw=.5,zorder=3)
            ax.set(xlim=(-1,35),ylim=(low,high),xlabel='U.S. News rank, 2027');ax.set_title(TITLES[rank]+' · '+title,loc='left',fontsize=16,pad=14);style_money(ax)
            texts=[ax.text(r.usnews_rank_2027,r[col],name(r.college),fontsize=10,weight='bold' if r.college in FOCUS else 'normal',color=RED if r.college==FOCUS[0] else INK) for _,r in h.iterrows()]
            np.random.seed(42);adjust_text(texts,ax=ax,expand=(1.15,1.3),force_text=(.4,.7),iter_lim=1200)
            resolve_label_overlaps(ax,texts,list(zip(h.usnews_rank_2027,h[col])))
            ax.set_ylabel('Nominal annual salary · dollars' if i==0 else 'Cost-adjusted annual salary · dollars')
    fig.suptitle('College rank and faculty purchasing power',x=.06,y=.98,ha='left',fontsize=28,weight='bold')
    fig.text(.06,.945,f'{year}–{str(year+1)[-2:]} salaries and {year} regional prices · columns show academic rank · identical axes down each column · all 30 colleges labeled',fontsize=15)
    finish(fig,'college_rank_and_salary',f'Sources: NCES IPEDS; BEA {year} RPP; U.S. News 2027 ranks via College Kickstart. Red: CMC. Bold: the six focal colleges.\nNine-month-equivalent institutional means; ranks and ties preserved. Cost-adjusted salary = salary ÷ (RPP/100).\nEach column compares the same schools with identical axes. This descriptive association is not a causal estimate.')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--legacy',action='store_true');args=parser.parse_args()
    d=pd.read_csv(ROOT/'data/processed/combined_long.csv');year=int(d.loc[d.salary_cost_adjusted.notna(),'year'].max())
    comparison(d,year);long_run(d);relative_trends(d);ranking_relationship(d,year)
    if args.legacy:
        import make_legacy_figures as legacy
        legacy.FIG=FIG/'legacy';legacy.FIG.mkdir(exist_ok=True);legacy.main()
    print('Generated four main figures, as PNG.')
if __name__=='__main__':main()
