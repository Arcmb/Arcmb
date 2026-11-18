"""Small offline XLSX/UTF-8 CSV template exporter; never evaluates spreadsheet formulas."""
import csv, io, zipfile
from xml.sax.saxutils import escape

MIME='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
def col(n):
 s=''
 while n:n,r=divmod(n-1,26);s=chr(65+r)+s
 return s

def export(headers,rows=None,kind='xlsx',guide=None,extra_sheets=None,first_name='Dados'):
 rows=rows or []
 if not 1<=len(headers)<=300:raise ValueError('Selecione entre 1 e 300 colunas. Divida campos em mais de um lote.')
 if kind=='csv':
  out=io.StringIO();w=csv.writer(out,delimiter=';',lineterminator='\r\n')
  def safe(v):
   s=str(v)if v is not None else ''
   return "'"+s if s.lstrip().startswith(('=','+','-','@')) else s
  w.writerow([safe(x)for x in headers]);w.writerows([[safe(x)for x in row]for row in rows]);return ('\ufeff'+out.getvalue()).encode('utf-8'),'text/csv; charset=utf-8'
 if kind!='xlsx':raise ValueError('Use formato XLSX ou CSV.')
 ns='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
 def cell(v,r,c,style=0):
  if v is None:return ''
  a=f'r="{col(c)}{r}" s="{style}"'
  if type(v) in (int,float):return f'<c {a}><v>{v}</v></c>'
  # Inline strings deliberately prevent execution of formula-like text.
  return f'<c {a} t="inlineStr"><is><t xml:space="preserve">{escape(str(v))}</t></is></c>'
 def sheet(h,rr,filter_on=True):
  records=[h]+rr
  cols=''.join(f'<col min="{i}" max="{i}" width="{36 if i==1 else 24}" customWidth="1"/>'for i in range(1,len(h)+1))
  body=''.join(f'<row r="{i}" ht="{46 if i==1 else 22}" customHeight="1">'+''.join(cell(v,i,j,1 if i==1 else 0)for j,v in enumerate(row,1))+'</row>'for i,row in enumerate(records,1))
  af=f'<autoFilter ref="A1:{col(len(h))}{max(len(records),2)}"/>'if filter_on else ''
  binary_cols=[col(i)for i,name in enumerate(h,1)if str(name).startswith('Acerto/erro questão ')]
  validations=(''.join(f'<dataValidation type="whole" operator="between" allowBlank="1" showErrorMessage="1" showInputMessage="1" errorStyle="stop" errorTitle="Use 1 ou 0" error="1 = acerto; 0 = erro; vazio = não informado." promptTitle="Resultado da questão" prompt="Digite 1 para acerto ou 0 para erro. Deixe vazio se não informado." sqref="{c}2:{c}5001"><formula1>0</formula1><formula2>1</formula2></dataValidation>'for c in binary_cols))
  validation_xml=f'<dataValidations count="{len(binary_cols)}">{validations}</dataValidations>'if binary_cols else ''
  return f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="{ns}"><sheetViews><sheetView workbookViewId="0" showGridLines="0"><pane ySplit="1" topLeftCell="A2" state="frozen"/></sheetView></sheetViews><sheetFormatPr defaultRowHeight="22"/><cols>{cols}</cols><sheetData>{body}</sheetData>{af}{validation_xml}</worksheet>'
 sheets=[(first_name,sheet(headers,rows))]
 for name,columns,records in (extra_sheets or []):
  sheets.append((name,sheet(columns,records)))
 if guide:sheets.append(('Como preencher',sheet(['Campo / orientação','Explicação'],guide,False)))
 parts={
 '_rels/.rels':'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
 'xl/workbook.xml':f'<workbook xmlns="{ns}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'+''.join(f'<sheet name="{name}" sheetId="{i}" r:id="rId{i}"/>'for i,(name,_)in enumerate(sheets,1))+'</sheets></workbook>',
 'xl/_rels/workbook.xml.rels':'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'+''.join(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>'for i in range(1,len(sheets)+1))+f'<Relationship Id="rId{len(sheets)+1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>',
 'xl/styles.xml':f'<styleSheet xmlns="{ns}"><fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><color rgb="FFFFFFFF"/><sz val="11"/><name val="Calibri"/></font></fonts><fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF554485"/><bgColor indexed="64"/></patternFill></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"><alignment vertical="center" wrapText="1"/></xf><xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"><alignment vertical="center" wrapText="1"/></xf></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>',
 '[Content_Types].xml':'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'+''.join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'for i in range(1,len(sheets)+1))+'</Types>'}
 for i,(_,xml)in enumerate(sheets,1):parts[f'xl/worksheets/sheet{i}.xml']=xml
 out=io.BytesIO()
 with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED)as z:
  for path,text in parts.items():z.writestr(path,text.encode('utf-8'))
 return out.getvalue(),MIME
