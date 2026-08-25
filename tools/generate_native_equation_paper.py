from pathlib import Path
import os, math, subprocess, zipfile
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyBboxPatch, FancyArrowPatch, Arc
from matplotlib.font_manager import FontProperties
from docx import Document
from docx.shared import Cm, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn

ROOT = Path(__file__).resolve().parents[1]
OUTDIR = ROOT / 'artifacts'
ASSET = OUTDIR / 'native_equation_assets'
OUTDIR.mkdir(parents=True, exist_ok=True)
ASSET.mkdir(parents=True, exist_ok=True)
MD = OUTDIR / 'native_equation_paper.md'
OUT = OUTDIR / '95式电磁激光仿真训练模型结构与原理说明_无乱码_原生公式版.docx'
REPORT = OUTDIR / '95式电磁激光仿真训练模型_原生公式验证报告.txt'

font_path = subprocess.check_output(['fc-match','-f','%{file}','Noto Sans CJK SC']).decode('utf-8').strip()
if not font_path or not Path(font_path).exists():
    raise RuntimeError('Noto CJK font not found; cannot safely render Chinese diagrams')
CJK = FontProperties(fname=font_path)


def savefig(fig,name):
    p=ASSET/name
    fig.savefig(p,dpi=240,bbox_inches='tight',facecolor='white')
    plt.close(fig)
    return p

def box(ax,x,y,w,h,text,fs=9):
    ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0.02,rounding_size=0.03',facecolor='#F7F7F7',edgecolor='black',linewidth=1.1))
    ax.text(x+w/2,y+h/2,text,ha='center',va='center',fontsize=fs,fontproperties=CJK)

def arrow(ax,a,b):
    ax.add_patch(FancyArrowPatch(a,b,arrowstyle='-|>',mutation_scale=12,linewidth=1.1,color='black'))

def make_figs():
    figs={}
    fig,ax=plt.subplots(figsize=(10,3.2)); ax.set_xlim(0,11); ax.set_ylim(0,4); ax.axis('off')
    box(ax,.2,1.45,1.35,.9,'锂电池组\n+BMS'); box(ax,1.9,1.45,1.5,.9,'扳机/模式\n输入'); box(ax,3.8,1.45,1.6,.9,'控制器/\n驱动电路')
    box(ax,6.0,2.35,1.6,.8,'电磁执行\n支路'); box(ax,6.0,.55,1.6,.8,'激光输出\n支路'); box(ax,8.2,2.35,1.5,.8,'机械动作\n反馈'); box(ax,8.2,.55,1.5,.8,'定向光学\n反馈')
    for a,b in [((1.55,1.9),(1.9,1.9)),((3.4,1.9),(3.8,1.9)),((5.4,2.0),(6.0,2.75)),((5.4,1.8),(6.0,.95)),((7.6,2.75),(8.2,2.75)),((7.6,.95),(8.2,.95))]: arrow(ax,a,b)
    ax.text(5.5,3.55,'系统总体能量与信号传递关系',ha='center',fontsize=12,fontproperties=CJK)
    figs['system']=savefig(fig,'fig01_system.png')

    fig,ax=plt.subplots(figsize=(10,3)); ax.set_xlim(0,12); ax.set_ylim(0,4); ax.axis('off')
    ax.add_patch(FancyBboxPatch((.5,1.2),10.5,1.35,boxstyle='round,pad=.04,rounding_size=.12',facecolor='white',edgecolor='black',linewidth=1.2))
    ax.add_patch(Rectangle((.8,1.45),2.2,.85,facecolor='#f0f0f0',edgecolor='black')); ax.text(1.9,1.88,'电池/BMS',ha='center',va='center',fontproperties=CJK)
    ax.add_patch(Rectangle((3.4,1.45),4.2,.85,facecolor='#f7f7f7',edgecolor='black')); ax.text(5.5,1.88,'控制与电磁执行区域',ha='center',va='center',fontproperties=CJK)
    ax.add_patch(Rectangle((8.0,1.45),2.0,.85,facecolor='#f0f0f0',edgecolor='black')); ax.text(9.0,1.88,'激光/前端输出',ha='center',va='center',fontproperties=CJK)
    arrow(ax,(10.0,1.88),(11.4,1.88)); ax.text(10.75,2.2,'光束',ha='center',fontproperties=CJK,fontsize=9)
    box(ax,4.5,.15,2.0,.65,'扳机与握持区',8); arrow(ax,(5.5,.8),(5.5,1.45))
    figs['layout']=savefig(fig,'fig02_layout.png')

    fig,ax=plt.subplots(figsize=(9,4)); ax.set_xlim(0,11); ax.set_ylim(0,5); ax.axis('off')
    ax.add_patch(Rectangle((1.0,.8),8.0,3.3,facecolor='white',edgecolor='black',linewidth=1.3))
    ax.add_patch(Rectangle((1.25,1.1),2.0,2.7,facecolor='#e8e8e8',edgecolor='black')); ax.text(2.25,2.45,'固定铁芯',ha='center',va='center',fontproperties=CJK)
    ax.add_patch(Rectangle((3.45,1.2),2.8,2.5,facecolor='#f7f7f7',edgecolor='black'))
    for y in [1.5,1.85,2.2,2.55,2.9,3.25]: ax.plot([3.7,6.0],[y,y],color='black',lw=1)
    ax.text(4.85,3.9,'励磁线圈',ha='center',fontproperties=CJK)
    ax.add_patch(Rectangle((6.8,1.7),2.4,1.5,facecolor='#ececec',edgecolor='black')); ax.text(8.0,2.45,'动铁芯/衔铁',ha='center',va='center',fontproperties=CJK)
    ax.text(6.52,2.45,'g',fontsize=11); arrow(ax,(9.25,2.45),(10.35,2.45)); ax.text(10.0,2.75,'x',fontsize=11)
    xs=[8.0,8.2,8.4,8.6,8.8,9.0,9.2,9.4]; ys=[1.45,1.18,1.45,1.18,1.45,1.18,1.45,1.18]; ax.plot(xs,ys,color='black',lw=1.2); ax.text(9.0,.75,'复位弹簧',ha='center',fontproperties=CJK,fontsize=9)
    ax.text(.3,2.4,'磁轭',rotation=90,va='center',fontproperties=CJK)
    figs['solenoid']=savefig(fig,'fig03_solenoid.png')

    fig,ax=plt.subplots(figsize=(9,3.8)); ax.set_xlim(0,10); ax.set_ylim(0,5); ax.axis('off')
    ax.text(1.0,4.35,'+V',fontsize=11); ax.plot([1.2,1.2],[4.1,3.55],color='black')
    xs=[1.2+i*.012 for i in range(251)]; ys=[3.2+.24*math.sin(2*math.pi*5*i/250) for i in range(251)]; ax.plot(xs,ys,color='black'); ax.text(2.7,3.7,'电磁线圈',fontproperties=CJK,ha='center')
    ax.plot([4.2,4.2],[3.2,2.45],color='black'); ax.add_patch(Rectangle((3.65,1.45),1.1,.9,facecolor='white',edgecolor='black')); ax.text(4.2,1.9,'MOSFET',ha='center',va='center',fontsize=9)
    ax.plot([4.2,4.2],[1.45,.7],color='black'); ax.text(3.85,.35,'GND')
    ax.plot([1.2,4.2],[.7,.7],color='black'); ax.plot([1.2,1.2],[3.2,2.65],color='black'); ax.plot([1.2,7.2],[2.65,2.65],color='black'); ax.plot([7.2,7.2],[2.65,3.2],color='black'); ax.plot([7.2,4.2],[3.2,3.2],color='black')
    ax.text(5.7,2.95,'续流/钳位支路',fontproperties=CJK,ha='center',fontsize=9); arrow(ax,(2.6,1.9),(3.65,1.9)); ax.text(2.4,2.15,'控制信号',fontproperties=CJK,ha='center',fontsize=9)
    figs['driver']=savefig(fig,'fig04_driver.png')

    fig,ax=plt.subplots(figsize=(10,3.5)); ax.set_xlim(0,11); ax.set_ylim(0,4); ax.axis('off')
    box(ax,.3,1.35,1.5,.9,'控制/电源'); box(ax,2.25,1.35,1.7,.9,'恒流驱动器'); box(ax,4.45,1.35,1.7,.9,'激光二极管'); arrow(ax,(1.8,1.8),(2.25,1.8)); arrow(ax,(3.95,1.8),(4.45,1.8))
    ax.add_patch(Arc((7.25,1.8),.55,1.5,theta1=-90,theta2=90,lw=1.4)); ax.add_patch(Arc((7.25,1.8),.55,1.5,theta1=90,theta2=270,lw=1.4)); ax.text(7.25,.7,'准直透镜',ha='center',fontproperties=CJK,fontsize=9)
    for dy in [-.35,0,.35]: ax.plot([6.15,7.0],[1.8,1.8+dy],color='black'); ax.plot([7.5,10.3],[1.8+dy,1.8+dy],color='black')
    ax.text(8.9,2.55,'准直后的方向性光束',ha='center',fontproperties=CJK,fontsize=9)
    figs['laser']=savefig(fig,'fig05_laser.png')

    fig,ax=plt.subplots(figsize=(9,3.2)); ax.set_xlim(-5,5); ax.set_ylim(-2.1,2.1); ax.axis('off')
    z=[-4+i*.04 for i in range(201)]; w=[.34*math.sqrt(1+(zz/1.35)**2) for zz in z]
    ax.plot(z,w,color='black',lw=1.3); ax.plot(z,[-q for q in w],color='black',lw=1.3); ax.plot([-4.5,4.5],[0,0],color='black',lw=.8); arrow(ax,(0,0),(4.65,0)); ax.text(4.48,-.3,'z',fontsize=11); ax.text(.1,.52,'w₀',fontsize=11); ax.text(3.25,1.65,'θ',fontsize=11)
    figs['gaussian']=savefig(fig,'fig06_gaussian.png')
    return figs

figs=make_figs()

md = r'''---
title: "95式电磁—激光仿真训练模型关键模块结构与工作原理分析"
lang: zh-CN
---

**摘 要：** 本文以现有95式外形仿真训练模型的拆解照片、锂电池组件、线束连接以及管状执行总成为基础，对系统结构和关键工作机理进行分析。实物能够确认装置采用电池供能，并包含保护/管理电路、主电源线、多芯线束、前端管状组件及安装定位结构；电磁铁和激光器的具体型号及内部安装位置尚未完全拆解确认。为避免将功能推断写成既定事实，本文把电磁执行与激光输出作为功能性模型处理，重点对磁路、电磁力、电气瞬态、机械运动、线圈温升、半导体激光电光转换、高斯光束传播和光轴偏差等关系进行校核，并给出公式适用条件与测试验证方法。

**关键词：** 仿真训练模型；电磁铁；磁共能；机电耦合；半导体激光器；高斯光束

# 1 引言

电磁执行机构的动态响应本质上是电路、磁场与机械运动相互耦合的过程。已有研究表明，电磁吸力与磁路结构、气隙和线圈电流密切相关，动态响应还受到运动质量、弹簧预紧、涡流和焦耳热等因素影响[1-5]。国外研究进一步从磁阻参数识别、多物理场建模、驱动电压和涡流损耗等方面对电磁执行器进行了分析[6-9]。这些研究用于支撑本文的基本理论关系，但其中的几何参数和性能指标不直接套用于本模型。

# 2 系统总体组成与功能布置

根据现有照片，可以确认的实物包括外部承载骨架、弹匣形电池仓、圆柱锂电池组及保护板、主电源线与检测线束、管状执行总成、前端金属管和安装支架。由此可将系统抽象为电源与保护、输入与控制、电磁执行、激光输出以及结构定位五个功能层。

![](''' + str(figs['system']) + r'''){width=85%}

**图1 系统总体能量与信号传递关系**

![](''' + str(figs['layout']) + r'''){width=85%}

**图2 模型内部功能区二维布置示意图**

# 3 电磁执行模块理论模型

## 3.1 结构组成与磁路模型

典型直线电磁铁由励磁线圈、固定铁芯、动铁芯或衔铁、磁轭、导向结构、工作气隙和复位弹簧组成。线圈通电后建立磁通，衔铁受到朝向磁阻减小方向的电磁力；当电磁力超过弹簧预紧、摩擦及外部负载后，衔铁开始运动。

![](''' + str(figs['solenoid']) + r'''){width=80%}

**图3 直线电磁铁结构与动作原理示意图**

对于由多个材料区段组成的简化磁路，总磁阻宜写成各段磁阻之和：

$$\mathcal{R}_m=\sum_i\frac{\ell_i}{\mu_i A_i}\qquad (1)$$

磁动势为 $NI$ 时，忽略漏磁并假定磁通在主磁路中连续，则

$$\Phi=\frac{NI}{\mathcal{R}_m}\qquad (2)$$

$$B_g\approx\frac{\Phi}{A_g}\qquad (3)$$

若气隙磁阻占主导，则

$$\mathcal{R}_g\approx\frac{g}{\mu_0 A_g}\qquad (4)$$

在气隙磁场近似均匀、边缘效应较小且铁磁材料未明显饱和时，气隙吸力可用 Maxwell 应力近似为

$$F_e\approx\frac{B_g^2A_g}{2\mu_0}\qquad (5)$$

式（5）主要用于趋势分析。实际电磁铁存在漏磁、边缘磁通、磁滞和饱和，应以实测力—位移数据或有限元结果修正。

## 3.2 磁共能与位置相关电感

更一般的电磁力可由磁共能表示：

$$F_e(i,x)=\left.\frac{\partial W_m'(i,x)}{\partial x}\right|_i\qquad (6)$$

在线性磁路近似下，若磁链满足 $\lambda=L(x)i$，则

$$W_m'(i,x)=\frac{1}{2}L(x)i^2\qquad (7)$$

$$F_e=\frac{1}{2}i^2\frac{\mathrm{d}L(x)}{\mathrm{d}x}\qquad (8)$$

若定义 $x$ 朝气隙减小方向为正，则电磁力趋向于使系统电感增大；若坐标方向相反，力的符号应随坐标定义调整。

## 3.3 线圈电气动态

原有简单关系 $u=Ri+L\,\mathrm{d}i/\mathrm{d}t$ 只在位置固定且电感近似不变时成立。更一般的端电压关系应写为

$$u=Ri+\frac{\mathrm{d}\lambda(i,x)}{\mathrm{d}t}\qquad (9)$$

若在某一工作区间近似取 $\lambda=L(x)i$，则

$$u=Ri+L(x)\frac{\mathrm{d}i}{\mathrm{d}t}+i\frac{\mathrm{d}L(x)}{\mathrm{d}x}\dot{x}\qquad (10)$$

其中第三项表示衔铁运动引起的运动反电动势。只有在运动尚未开始或 $L$ 近似常数时，才可简化为

$$u=Ri+L\frac{\mathrm{d}i}{\mathrm{d}t}\qquad (11)$$

对于直流阶跃电压 $U$、初始电流为0的固定电感模型，

$$i(t)=\frac{U}{R}\left(1-e^{-t/\tau_e}\right),\qquad \tau_e=\frac{L}{R}\qquad (12)$$

其10%—90%电流上升时间为

$$t_{r,10-90}=\tau_e\ln 9\approx2.197\tau_e\qquad (13)$$

## 3.4 机械运动模型

将动铁芯和连接件等效为单自由度系统，并分别考虑阻尼、复位弹簧、摩擦和外部负载，可写为

$$m\ddot{x}=F_e(i,x)-c\dot{x}-k(x-x_0)-F_f(\dot{x})-F_L\qquad (14)$$

该式适用于宏观位移阶段；若存在刚性碰撞或限位，需要增加接触模型或通过试验直接测量。

## 3.5 铜耗、温升与驱动保护

对于脉冲或周期电流，线圈铜耗应采用有效值：

$$P_{Cu}=I_{rms}^2R(T)\qquad (15)$$

铜电阻随温度的变化可近似写为

$$R(T)=R(T_0)\left[1+\alpha_{Cu}(T-T_0)\right]\qquad (16)$$

若采用一阶集中参数热模型，

$$C_\theta\frac{\mathrm{d}T}{\mathrm{d}t}=P_{loss}-\frac{T-T_a}{R_\theta}\qquad (17)$$

稳态温升近似为

$$\Delta T_{ss}\approx P_{loss}R_\theta\qquad (18)$$

MOSFET 驱动感性线圈时需要设置续流二极管、TVS 或其他钳位支路，以限制关断时的感应电压。

![](''' + str(figs['driver']) + r'''){width=78%}

**图4 电磁线圈 MOSFET 驱动与续流/钳位保护示意图**

# 4 激光模块理论模型

## 4.1 结构与电光转换

半导体激光模块通常由激光二极管、恒流驱动器、准直/整形透镜、安装座和出光窗口组成。国内关于半导体激光准直和束散角测试的研究表明，激光二极管快、慢轴发散特性明显不同，工程上常借助非球面透镜或多片光学系统进行准直[11-13]；器件物理和光束传播可参考专业著作及相关理论研究[14-16]。

![](''' + str(figs['laser']) + r'''){width=82%}

**图5 激光二极管模块及准直光路示意图**

在阈值以上且工作区间不太宽时，输出光功率可作线性近似：

$$P_{opt}\approx\eta_s\left(I-I_{th}\right),\qquad I>I_{th}\qquad (19)$$

其中 $\eta_s=\mathrm{d}P_{opt}/\mathrm{d}I$ 为斜率效率，常用单位为 W/A，并非无量纲效率。电光转换效率可定义为

$$\eta_{eo}=\frac{P_{opt}}{V_fI}\qquad (20)$$

## 4.2 高斯光束传播

在近轴、基模高斯光束近似下，束腰位于 $z_0$ 处时，1/e² 光强半径为

$$w(z)=w_0\sqrt{1+\left(\frac{z-z_0}{z_R}\right)^2}\qquad (21)$$

$$z_R=\frac{\pi w_0^2}{\lambda}\qquad (22)$$

理想高斯光束的远场半发散角为

$$\theta_0=\frac{\lambda}{\pi w_0}\qquad (23)$$

对于实际非理想光束，可引入 $M^2$ 因子：

$$w(z)=w_0\sqrt{1+\left[\frac{M^2\lambda(z-z_0)}{\pi w_0^2}\right]^2}\qquad (24)$$

$$\theta=\frac{M^2\lambda}{\pi w_0}\qquad (25)$$

若使用 1/e² 光强直径，则

$$D(z)=2w(z)\qquad (26)$$

![](''' + str(figs['gaussian']) + r'''){width=70%}

**图6 高斯光束束腰与远场发散示意图**

ISO 11146 使用二阶矩方法定义光束宽度、发散角和光束传播比。正式测试时不应把几何光斑直径与标准二阶矩光束宽度混用[17]。

## 4.3 光轴偏差与两点估算

若距离 $L$ 处光斑中心相对机械基准轴横向偏移 $\Delta y$，则

$$\alpha=\arctan\left(\frac{\Delta y}{L}\right)\approx\frac{\Delta y}{L}\quad(\alpha\ll1)\qquad (27)$$

工程上宜用 rad 或 mrad 表示指向误差，不建议将 $\Delta y/L\times100\%$ 直接称为“相对指向偏差”。

在远场线性近似下，利用两个截面的光斑直径估算全角发散角 $\Theta$：

$$\Theta\approx\frac{D_2-D_1}{z_2-z_1},\qquad \theta=\frac{\Theta}{2}\qquad (28)$$

该两点法不适用于束腰附近；规范的 $M^2$ 和发散角测试应采用多截面拟合并参考 ISO 11146[17]。

# 5 电磁—激光协同工作链路

从控制逻辑上，电磁支路与激光支路通常是并行输出，不宜把两支路的所有延迟简单相加为一个统一响应时间。可分别定义机械反馈延迟与激光输出延迟：

$$t_{em}=t_{ctrl}+t_e+t_m\qquad (29)$$

$$t_{laser}=t_{ctrl}+t_{drv}+t_{opt}\qquad (30)$$

两种反馈之间的同步误差为

$$\Delta t=t_{laser}-t_{em}\qquad (31)$$

# 6 测试与验证方法

为验证上述功能性模型，可在确认接口与额定参数后，同步采集扳机信号、线圈电流、外部可观测位移/振动以及激光输出信号。

电流或位移的10%—90%上升时间定义为

$$t_{r,10-90}=t_{90\%}-t_{10\%}\qquad (32)$$

有效行程内平均速度为

$$\bar{v}=\frac{s}{\Delta t}\qquad (33)$$

一次触发窗口内的电输入能量为

$$E_e=\int_{t_1}^{t_2}u(t)i(t)\,\mathrm{d}t\qquad (34)$$

多次指向测试可用平均指向角与样本标准差评价重复性：

$$\bar{\alpha}=\frac{1}{n}\sum_{j=1}^{n}\alpha_j\qquad (35)$$

$$\sigma_\alpha=\sqrt{\frac{1}{n-1}\sum_{j=1}^{n}\left(\alpha_j-\bar{\alpha}\right)^2}\qquad (36)$$

# 7 结论

本文对原有电磁与激光公式进行了系统校核。主要修正包括：用分段磁阻与磁共能表达替代过度简化的平均磁路描述；在线圈电压方程中补充位置相关电感引起的运动反电动势；明确 RL 阶跃公式只适用于固定位置和近似恒定电感条件；使用 $I_{rms}^2R$ 描述周期电流铜耗并补充一阶热模型；在激光部分区分理想高斯光束与 $M^2$ 修正模型；将原“相对指向偏差百分比”改为更规范的角度误差 $\alpha$；同时将电磁与激光两条并行支路分别建模。

# 参考文献

[1] 王淑红, 肖旭亮, 熊光煜. 直流恒力电磁铁特性[J]. 机械工程学报, 2008, 44(2): 244-247.  
[2] 赵建辉, 周勇, 石勇, 等. 共轨喷油器高速电磁阀动态响应试验研究[J]. 哈尔滨工程大学学报, 2018, 39(1): 74-79. DOI:10.11990/jheu.201611063.  
[3] 赵建辉, 陈文菲, 杨贵春, 陈敬炎. 高速电磁阀能量分布和动态响应耦合关系仿真[J]. 西南交通大学学报, 2024, 59(6): 1398-1405. DOI:10.3969/j.issn.0258-2724.20220452.  
[4] 李英杰, 陈川, 张瑜, 等. 电磁铁传热特性及散热优化的数值模拟[J]. 重庆大学学报, 2024, 47(5): 24-36. DOI:10.11835/j.issn.1000.582X.2024.05.005.  
[5] 孙雷强, 庄劲武, 王冲, 等. 基于联合仿真的断路器合闸电磁铁的动态特性研究[J]. 电气工程学报, 2023, 18(1): 104-110. DOI:10.11985/2023.01.011.  
[6] XU Y, JONES B. A simple means of predicting the dynamic response of electromagnetic actuators[J]. Mechatronics, 1997, 7(7): 589-598. DOI:10.1016/S0957-4158(97)00028-7.  
[7] LIU Q, BO H, QIN B. Experimental study and numerical analysis on electromagnetic force of direct action solenoid valve[J]. Nuclear Engineering and Design, 2010, 240(12): 4031-4036. DOI:10.1016/j.nucengdes.2010.09.028.  
[8] ZHAO J, WANG M, WANG Z, et al. Different boost voltage effects on the dynamic response and energy losses of high-speed solenoid valves[J]. Applied Thermal Engineering, 2017, 123: 1494-1503. DOI:10.1016/j.applthermaleng.2017.05.117.  
[9] LIU P, ZHANG R, ZHAO Q, PENG S. Eddy Effect and Dynamic Response of High-Speed Solenoid Valve with Composite Iron Core[J]. Materials, 2023, 16(17): 5823. DOI:10.3390/ma16175823.  
[10] GEEPLUS. Push-Pull Solenoids[EB/OL]. https://www.geeplus.com/push-pull-solenoids/.  
[11] 谭佐军, 薛松, 康竟然, 陈海清. 激光引信中半导体激光器的准直及其测试[J]. 应用光学, 2007, 28(4): 454-457.  
[12] 聂建华, 王峻宁. 基于ZEMAX的半导体激光准直镜设计方法研究[J]. 红外, 2012, 33(3): 22-26.  
[13] 段园园, 吉晓, 阴万宏, 等. 一种大功率宽波段激光束散角的校准测试方法[J]. 应用光学, 2023, 44(2): 450-455. DOI:10.5768/JAO202344.0207004.  
[14] COLDREN L A, CORZINE S W, MASHANOVITCH M L. Diode Lasers and Photonic Integrated Circuits[M]. 2nd ed. Hoboken: Wiley, 2012. DOI:10.1002/9781118148167.  
[15] XU Q, HAN Y, CUI Z. Characteristic of laser diode beam propagation through a collimating lens[J]. Applied Optics, 2010, 49(3): 549-553. DOI:10.1364/AO.49.000549.  
[16] KOGELNIK H, LI T. Laser beams and resonators[J]. Applied Optics, 1966, 5(10): 1550-1567. DOI:10.1364/AO.5.001550.  
[17] ISO. ISO 11146-1:2021 Lasers and laser-related equipment—Test methods for laser beam widths, divergence angles and beam propagation ratios—Part 1: Stigmatic and simple astigmatic beams[S]. Geneva: ISO, 2021.  
[18] COHERENT CORP. Diode Laser Modules[EB/OL]. https://www.coherent.com/lasers/diode-modules.  
[19] 国家市场监督管理总局, 国家标准化管理委员会. GB/T 7247.1-2024 激光产品的安全 第1部分：设备分类和要求[S]. 北京: 中国标准出版社, 2024.  
[20] 国家市场监督管理总局, 国家标准化管理委员会. GB 31241-2022 便携式电子产品用锂离子电池和电池组 安全技术规范[S]. 北京: 中国标准出版社, 2022.
'''
MD.write_text(md,encoding='utf-8')

subprocess.run(['pandoc',str(MD),'-o',str(OUT),'--from=markdown+tex_math_dollars','--to=docx'],check=True)

# Post-process styles without touching OMML equation objects.
doc=Document(OUT)
sec=doc.sections[0]; sec.top_margin=Cm(2.4); sec.bottom_margin=Cm(2.3); sec.left_margin=Cm(2.6); sec.right_margin=Cm(2.4)
normal=doc.styles['Normal']; normal.font.name='宋体'; normal._element.rPr.rFonts.set(qn('w:eastAsia'),'宋体'); normal.font.size=Pt(10.5)
for styname,size,font in [('Title',18,'黑体'),('Heading 1',15,'黑体'),('Heading 2',12.5,'黑体')]:
    if styname in doc.styles:
        st=doc.styles[styname]; st.font.name=font; st._element.rPr.rFonts.set(qn('w:eastAsia'),font); st.font.size=Pt(size)
for p in doc.paragraphs:
    if p.style.name=='Normal' and p.text.strip():
        p.alignment=WD_ALIGN_PARAGRAPH.JUSTIFY
        if not p.text.startswith(('图','参考文献')):
            p.paragraph_format.first_line_indent=Pt(21)
doc.save(OUT)

# Validate: formulas must be native Office Math, not equation images.
with zipfile.ZipFile(OUT,'r') as z:
    xml=z.read('word/document.xml').decode('utf-8')
    math_count=xml.count('<m:oMath')
    media=[n for n in z.namelist() if n.startswith('word/media/')]
if math_count < 30:
    raise RuntimeError(f'Native equation validation failed: only {math_count} OMML nodes')
if any('eq_' in n.lower() for n in media):
    raise RuntimeError('Equation images detected; expected native OMML equations only')
REPORT.write_text(f'Native Word equation objects (OMML): {math_count}\nDiagram media files: {len(media)}\nChinese diagram font: {font_path}\nEquation images detected: NO\n',encoding='utf-8')
print(OUT)
print(REPORT)
