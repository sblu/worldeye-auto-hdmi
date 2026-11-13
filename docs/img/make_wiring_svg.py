import sys
out=sys.argv[1]
W,H=980,740
s=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" font-family="Helvetica,Arial,sans-serif">',
   f'<rect width="{W}" height="{H}" fill="#ffffff"/>',
   '<text x="24" y="34" font-size="20" font-weight="bold" fill="#111">W25Q32 flash (in the SOIC-8 clip) to Raspberry Pi 40-pin header</text>',
   '<text x="24" y="56" font-size="13" fill="#444">Globe unplugged. The Pi powers the chip through the clip. Pin 3 link is needed for writing only.</text>']
# chip top view
cx,cy,cw,ch=40,130,120,150
s.append(f'<rect x="{cx}" y="{cy}" width="{cw}" height="{ch}" rx="6" fill="#2b2b2b"/>')
s.append(f'<circle cx="{cx+16}" cy="{cy+16}" r="6" fill="#bbbbbb"/>')
s.append(f'<text x="{cx+cw/2}" y="{cy+ch/2}" font-size="13" fill="#fff" text-anchor="middle">W25Q32</text>')
s.append(f'<text x="{cx+cw/2}" y="{cy+ch/2+16}" font-size="11" fill="#ccc" text-anchor="middle">top view</text>')
for i in range(4):
    y=cy+24+i*34
    s.append(f'<rect x="{cx-16}" y="{y-6}" width="16" height="12" fill="#999"/><text x="{cx-22}" y="{y+4}" font-size="12" text-anchor="end" fill="#111">{i+1}</text>')
    s.append(f'<rect x="{cx+cw}" y="{y-6}" width="16" height="12" fill="#999"/><text x="{cx+cw+22}" y="{y+4}" font-size="12" fill="#111">{8-i}</text>')
s.append(f'<text x="{cx+cw/2}" y="{cy+ch+20}" font-size="12" fill="#444" text-anchor="middle">dot = pin 1</text>')
s.append(f'<text x="{cx+cw/2}" y="{cy+ch+36}" font-size="12" fill="#444" text-anchor="middle">(clip red wire)</text>')
# adapter column
ax=300
pins=[(1,'/CS','#d62728',24,'CE0 (GPIO8)'),(2,'DO','#1f77b4',21,'MISO (GPIO9)'),(3,'/WP','#9467bd',1,'3.3 V via 1 kΩ'),(4,'GND','#111111',25,'GND'),
      (5,'DI','#2ca02c',19,'MOSI (GPIO10)'),(6,'CLK','#ff7f0e',23,'SCLK (GPIO11)'),(7,'/HOLD',None,None,'not connected'),(8,'VCC','#e377c2',17,'3.3 V')]
s.append(f'<text x="{ax-70}" y="120" font-size="13" font-weight="bold" fill="#111">Chip pin (clip adapter)</text>')
ay=lambda n:150+(n-1)*62
for n,name,col,pp,lab in pins:
    y=ay(n)
    s.append(f'<rect x="{ax-70}" y="{y-16}" width="110" height="32" rx="4" fill="#f2f2f2" stroke="#888"/>')
    s.append(f'<text x="{ax-60}" y="{y+5}" font-size="14" fill="#111"><tspan font-weight="bold">{n}</tspan>  {name}</text>')
# header
hx,hy,rp=770,130,28
s.append(f'<text x="{hx-10}" y="{hy-22}" font-size="13" font-weight="bold" fill="#111">Raspberry Pi header</text>')
s.append(f'<text x="{hx-10}" y="{hy-7}" font-size="11" fill="#444">pin 1 = corner nearest the microSD slot</text>')
s.append(f'<rect x="{hx-18}" y="{hy}" width="76" height="{20*rp+8}" rx="4" fill="#1b5e20" opacity="0.12" stroke="#1b5e20"/>')
used={p[3]:p for p in pins if p[3]}
pos={}
for r in range(20):
    for c in range(2):
        pn=r*2+1+c; x=hx+c*40; y=hy+18+r*rp; pos[pn]=(x,y)
        col=used[pn][2] if pn in used else '#cfcfcf'
        s.append(f'<circle cx="{x}" cy="{y}" r="9" fill="{col}" stroke="#555"/>')
        if pn in used:
            s.append(f'<text x="{x}" y="{y+4}" font-size="10" text-anchor="middle" fill="#fff" font-weight="bold">{pn}</text>')
        elif pn in (2,39,40):
            tx=x-14 if c==0 else x+14; anc='end' if c==0 else 'start'
            s.append(f'<text x="{tx}" y="{y+4}" font-size="11" text-anchor="{anc}" fill="#444">{pn}</text>')
# wires
chan={1:None,2:610,3:728,4:550,5:640,6:580,8:520}
for n,name,col,pp,lab in pins:
    y=ay(n); x0=ax+40
    if pp is None:
        s.append(f'<text x="{x0+12}" y="{y+5}" font-size="13" fill="#777" font-style="italic">leave unconnected</text>'); continue
    px,py=pos[pp]
    if n==1:  # to right column: go over the top
        pts=[(x0,y),(480,y),(480,84),(955,84),(955,py),(px+9,py)]
    else:
        cxn=chan[n]; pts=[(x0,y),(cxn,y),(cxn,py),(px-24,py)]
        pts[-1]=(px-9,py)
    d=' '.join(f'{a},{b}' for a,b in pts)
    s.append(f'<polyline points="{d}" fill="none" stroke="{col}" stroke-width="3"/>')
    s.append(f'<text x="{x0+8}" y="{y-7}" font-size="11" fill="{col}">to Pi pin {pp}: {lab}</text>')
    if n==3:
        rx=652
        s.append(f'<rect x="{rx}" y="{y-9}" width="56" height="18" fill="#fff" stroke="{col}" stroke-width="2.5"/>')
        s.append(f'<text x="{rx+28}" y="{y+5}" font-size="12" text-anchor="middle" fill="#111" font-weight="bold">1 kΩ</text>')
# notes
ny=700
s.append(f'<text x="24" y="{ny}" font-size="13" fill="#111">Reading needs pins 1, 2, 4, 5, 6, 8 only. Writing also needs pin 3 pulled to 3.3 V through the resistor: the board holds /WP low</text>')
s.append(f'<text x="24" y="{ny+18}" font-size="13" fill="#111">with about 10 kΩ, and the chip refuses to unlock until it is high. Never connect anything here to a 5 V pin (Pi pins 2 and 4).</text>')
s.append('</svg>')
open(out,'w').write('\n'.join(s))
