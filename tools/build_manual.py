"""Build matching Japanese/English project guides from docs/manual/guide_*.json.

Documentation-only dependency: ReportLab. Japanese fonts default to Windows
Yu Gothic; use --font and --bold-font with suitable TTF/TTC fonts elsewhere.
Render and visually inspect both outputs before publishing a revised guide.
"""
import argparse
from html import escape
import json
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle, Preformatted

ROOT=Path(__file__).resolve().parents[1]
INK=colors.HexColor('#173047')
TEAL=colors.HexColor('#007F85')
PALE=colors.HexColor('#EDF5F6')
GREY=colors.HexColor('#526675')
WIDTH=A4[0]-34*mm


class NumberedCanvas(canvas.Canvas):
    """Write actual page totals after ReportLab has completed pagination."""
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.states=[]

    def showPage(self):
        self.states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total=len(self.states)
        for state in self.states:
            self.__dict__.update(state)
            self.setFont('Helvetica',7.5)
            self.setFillColor(GREY)
            self.drawRightString(A4[0]-17*mm,11*mm,f'{self._pageNumber} / {total}')
            super().showPage()
        super().save()


def build(language,args):
    data=json.loads((ROOT/f'docs/manual/guide_{language}.json').read_text(encoding='utf-8'))
    if language=='ja':
        regular,strong='Japanese','JapaneseBold'
        pdfmetrics.registerFont(TTFont(regular,args.font,subfontIndex=0))
        pdfmetrics.registerFont(TTFont(strong,args.bold_font,subfontIndex=0))
        wrap='CJK'
    else:
        if Path('C:/Windows/Fonts/arial.ttf').is_file():
            regular,strong='English','EnglishBold'
            pdfmetrics.registerFont(TTFont(regular,'C:/Windows/Fonts/arial.ttf'))
            pdfmetrics.registerFont(TTFont(strong,'C:/Windows/Fonts/arialbd.ttf'))
        else:
            regular,strong='Helvetica','Helvetica-Bold'
        wrap='LTR'
    styles={
        'body':ParagraphStyle('body',fontName=regular,fontSize=9.2,leading=15.1,
                             textColor=INK,wordWrap=wrap,spaceAfter=7),
        'small':ParagraphStyle('small',fontName=regular,fontSize=8.0,leading=12.5,
                              textColor=GREY,wordWrap=wrap,spaceAfter=6),
        'subtitle':ParagraphStyle('subtitle',fontName=strong,fontSize=13,leading=20,
                                 textColor=TEAL,wordWrap=wrap,spaceAfter=14),
        'h1':ParagraphStyle('h1',fontName=strong,fontSize=18,leading=26,
                           textColor=INK,wordWrap=wrap,spaceAfter=15),
        'cover':ParagraphStyle('cover',fontName=strong,fontSize=34,leading=43,
                              textColor=INK,spaceBefore=20,spaceAfter=17),
        'h2':ParagraphStyle('h2',fontName=strong,fontSize=11,leading=17,
                           textColor=TEAL,wordWrap=wrap,spaceBefore=9,spaceAfter=6,keepWithNext=True),
        'cell':ParagraphStyle('cell',fontName=regular,fontSize=7.9,leading=11.9,
                             textColor=INK,wordWrap=wrap),
        'th':ParagraphStyle('th',fontName=strong,fontSize=8,leading=12,
                           textColor=colors.white,wordWrap=wrap),
        'code':ParagraphStyle('code',fontName='Courier',fontSize=7.8,leading=11.2,textColor=INK),
    }
    story=[]

    def p(text,style='body'):
        value=escape(text).replace('\n','<br/>')
        def link(match):
            url=match.group(0)
            return '<link href="'+url+'" color="#007F85">'+url+'</link>'
        value=re.sub(r"https?://[A-Za-z0-9][A-Za-z0-9./_~%:#?=&;+\-]*",link,value)
        return Paragraph(value,styles[style])

    for number,chapter in enumerate(data['chapters'],1):
        if number>1:
            story.append(PageBreak())
        title=chapter['title'] if chapter.get('cover') else f'{number:02d}  {chapter["title"]}'
        story.append(p(title,'cover' if chapter.get('cover') else 'h1'))
        for block in chapter['blocks']:
            kind,values=block['kind'],block['args']
            if kind=='p':
                story.append(p(*values))
            elif kind=='h':
                story.append(p(values[0],'h2'))
            elif kind=='code':
                for line in values[0].splitlines():
                    if pdfmetrics.stringWidth(line,'Courier',7.8)>WIDTH-18:
                        raise ValueError('Command too wide: '+line)
                box=Table([[Preformatted(values[0].strip('\n'),styles['code'])]],colWidths=[WIDTH])
                box.setStyle(TableStyle([
                    ('BACKGROUND',(0,0),(-1,-1),PALE),('BOX',(0,0),(-1,-1),.4,colors.HexColor('#D1E3E6')),
                    ('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),
                    ('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),7),
                ]))
                story.extend([box,Spacer(1,10)])
            elif kind=='table':
                headers,rows,widths=values
                entries=[[p(str(c),'th') for c in headers]]+[[p(str(c),'cell') for c in row] for row in rows]
                table=Table(entries,colWidths=[WIDTH*w for w in widths],hAlign='LEFT',repeatRows=1)
                table.setStyle(TableStyle([
                    ('BACKGROUND',(0,0),(-1,0),INK),
                    ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,PALE]),
                    ('VALIGN',(0,0),(-1,-1),'TOP'),
                    ('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),
                    ('TOPPADDING',(0,0),(-1,-1),5.5),('BOTTOMPADDING',(0,0),(-1,-1),5.5),
                    ('LINEBELOW',(0,-1),(-1,-1),.4,colors.HexColor('#CCDCE0')),
                ]))
                story.extend([table,Spacer(1,8)])
            else:
                raise ValueError('Unknown guide block: '+kind)
    output=args.output_dir/f'PyRetinotopy_Experiment_Guide_{language}.pdf'
    output.parent.mkdir(parents=True,exist_ok=True)
    name=data.get('pdf_title','Project and Experiment Guide')
    doc=SimpleDocTemplate(str(output),pagesize=A4,rightMargin=17*mm,leftMargin=17*mm,
                         topMargin=21*mm,bottomMargin=19*mm,
                         title=f'PyRetinotopy {name} v{data["version"]}',author=data['author'],
                         subject='Retinotopic visual stimulation in Python and PsychoPy')

    def furniture(c,document):
        c.saveState()
        c.setStrokeColor(TEAL)
        c.setLineWidth(.8)
        c.line(17*mm,A4[1]-14*mm,A4[0]-17*mm,A4[1]-14*mm)
        c.setFont(strong,8)
        c.setFillColor(TEAL)
        c.drawString(17*mm,A4[1]-11*mm,'PyRetinotopy')
        c.setFont(regular,7.4)
        c.setFillColor(GREY)
        c.drawRightString(A4[0]-17*mm,A4[1]-11*mm,f'PROJECT AND EXPERIMENT GUIDE | {language.upper()} | v{data["version"]}')
        c.drawString(17*mm,11*mm,f'{data["date"]} / {data["author"]} / Python + PsychoPy')
        c.restoreState()

    doc.build(story,onFirstPage=furniture,onLaterPages=furniture,canvasmaker=NumberedCanvas)
    print(output.resolve())


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--language',choices=('ja','en','both'),default='both')
    parser.add_argument('--font',default='C:/Windows/Fonts/YuGothR.ttc')
    parser.add_argument('--bold-font',default='C:/Windows/Fonts/YuGothB.ttc')
    parser.add_argument('--output-dir',type=Path,default=ROOT/'docs')
    args=parser.parse_args()
    for language in (('ja','en') if args.language=='both' else (args.language,)):
        build(language,args)


if __name__=='__main__':
    main()
