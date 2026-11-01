from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import math, random
OUT = Path(__file__).parent/'assets'
W,H=1200,540
random.seed(29)
stars=[(random.randrange(W),random.randrange(H),random.random()*math.tau) for _ in range(65)]
fontpath='C:/Windows/Fonts/seguisb.ttf'
themes=[('welcome','WELCOME TO','AETHON','YOUR NEXT ADVENTURE',(168,144,255)),('mmorpg','AETHON','MMORPG','EXPLORE • PROGRESS • BELONG',(168,144,255)),('smp','VOLCANISM','SMP','SURVIVAL • BUILDING • FRIENDS',(255,169,97)),('soon','THE NEXT','CHAPTER','A NEW WORLD AWAITS',(103,224,223)),('rules','COMMUNITY','RULES','GOOD PEOPLE • GREAT WORLDS',(168,144,255)),('links','EXPLORE','AETHON','MODS • MODPACKS • SERVERS',(103,224,223))]
for key,line1,line2,sub,color in themes:
    frames=[]
    palette = None
    for i in range(150):
        phase=i/150*math.tau
        im=Image.new('RGB',(W,H),(10,15,30));d=ImageDraw.Draw(im)
        for y in range(H):
            glow=max(0,1-abs(y-260)/350)*.075
            d.line((0,y,W,y),fill=tuple(int(9+c*glow) for c in color))
        for x,y,p in stars:
            if 130 < x < 1070 and 65 < y < 455:continue
            v=.35+.4*(math.sin(phase+p)+1)/2
            d.ellipse((x,y,x+3,y+3),fill=tuple(int(c*v) for c in color))
        d.rounded_rectangle((20,20,W-21,H-21),radius=25,outline=tuple(int(c*.55) for c in color),width=3)
        d.text((600,137),line1,font=ImageFont.truetype(fontpath,104),fill=(250,251,255),anchor='mm')
        d.text((600,260),line2,font=ImageFont.truetype(fontpath,116),fill=(250,251,255),anchor='mm')
        d.text((600,367),sub,font=ImageFont.truetype(fontpath,43),fill=color,anchor='mm')
        d.line((240,418,960,418),fill=tuple(int(c*.35) for c in color),width=3)
        x=600+350*math.sin(phase)
        d.ellipse((x-6,412,x+6,424),fill=color)
        d.text((600,474),'MINECRAFT COMMUNITY',font=ImageFont.truetype(fontpath,42),fill=(215,226,243),anchor='mm')
        if palette is None:
            palette = im.quantize(colors=256)
        frames.append(im.quantize(palette=palette, dither=Image.Dither.NONE))
    frames[0].save(OUT/(key+'.gif'),save_all=True,append_images=frames[1:],duration=40,loop=0,optimize=False)
    if key=='mmorpg': im.resize((400,180)).save(OUT/'readability-preview.png')
    print(key,(OUT/(key+'.gif')).stat().st_size)
