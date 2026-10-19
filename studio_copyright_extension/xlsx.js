/* Minimal XLSX writer: inline text cells, external hyperlinks, ZIP STORE. No network dependencies. */
(() => {
  const enc = new TextEncoder();
  const xml = value => String(value ?? '').replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f]/g, '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&apos;');
  const crc = bytes => {let c=0xffffffff;for(const b of bytes){c^=b;for(let k=0;k<8;k++)c=(c>>>1)^((c&1)?0xedb88320:0);}return (c^0xffffffff)>>>0;};
  function zip(files) {
    const chunks=[], directory=[];let offset=0;
    for(const [name,text] of files){
      const n=enc.encode(name),data=enc.encode(text),sum=crc(data);
      const head=new Uint8Array(30+n.length),h=new DataView(head.buffer);
      h.setUint32(0,0x04034b50,true);h.setUint16(4,20,true);h.setUint32(14,sum,true);h.setUint32(18,data.length,true);h.setUint32(22,data.length,true);h.setUint16(26,n.length,true);head.set(n,30);
      const central=new Uint8Array(46+n.length),c=new DataView(central.buffer);
      c.setUint32(0,0x02014b50,true);c.setUint16(4,20,true);c.setUint16(6,20,true);c.setUint32(16,sum,true);c.setUint32(20,data.length,true);c.setUint32(24,data.length,true);c.setUint16(28,n.length,true);c.setUint32(42,offset,true);central.set(n,46);
      chunks.push(head,data);directory.push(central);offset+=head.length+data.length;
    }
    const size=directory.reduce((n,b)=>n+b.length,0),end=new Uint8Array(22),e=new DataView(end.buffer);
    e.setUint32(0,0x06054b50,true);e.setUint16(8,files.length,true);e.setUint16(10,files.length,true);e.setUint32(12,size,true);e.setUint32(16,offset,true);
    const out=new Uint8Array(offset+size+22);let position=0;
    for(const part of [...chunks,...directory,end]){out.set(part,position);position+=part.length;}return out;
  }
  function workbook(sheets){
    const files=[],types=[],names=[],rels=[];
    sheets.forEach((sheet,i)=>{
      const id=i+1,links=[];
      const rows=sheet.rows.map((row,r)=>'<row r="'+(r+1)+'">'+row.map((value,c)=>{
        let col='',n=c+1;while(n){n--;col=String.fromCharCode(65+n%26)+col;n=Math.floor(n/26);}const cell=col+(r+1);
        if(r>0 && /^https:\/\/(?:www\.youtube\.com\/watch\?v=|studio\.youtube\.com\/video\/)/.test(String(value)))links.push({cell,url:String(value)});
        return '<c r="'+cell+'" t="inlineStr"><is><t xml:space="preserve">'+xml(value)+'</t></is></c>';
      }).join('')+'</row>').join('');
      const linkXml=links.length?'<hyperlinks>'+links.map((l,j)=>'<hyperlink ref="'+l.cell+'" r:id="rId'+(j+1)+'"/>').join('')+'</hyperlinks>':'';
      files.push(['xl/worksheets/sheet'+id+'.xml','<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" state="frozen"/></sheetView></sheetViews><cols><col min="1" max="1" width="65" customWidth="1"/><col min="2" max="8" width="60" customWidth="1"/></cols><sheetData>'+rows+'</sheetData>'+linkXml+'</worksheet>']);
      if(links.length)files.push(['xl/worksheets/_rels/sheet'+id+'.xml.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'+links.map((l,j)=>'<Relationship Id="rId'+(j+1)+'" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" Target="'+xml(l.url)+'" TargetMode="External"/>').join('')+'</Relationships>']);
      names.push('<sheet name="'+xml(sheet.name)+'" sheetId="'+id+'" r:id="rId'+id+'"/>');
      rels.push('<Relationship Id="rId'+id+'" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet'+id+'.xml"/>');
      types.push('<Override PartName="/xl/worksheets/sheet'+id+'.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>');
    });
    files.push(['[Content_Types].xml','<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'+types.join('')+'</Types>']);
    files.push(['_rels/.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>']);
    files.push(['xl/workbook.xml','<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'+names.join('')+'</sheets></workbook>']);
    files.push(['xl/_rels/workbook.xml.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'+rels.join('')+'</Relationships>']);
    return zip(files);
  }
  function classify(text){
    text=String(text||'').replace(/\s+/g,' ').trim();
    if(/^(?:none|无|没有|无限制|—|–|-|なし|없음|нет)$/i.test(text))return null;
    const negative=/^(?:no copyright|无版权问题|没有版权问题|未发现版权)/i.test(text);
    const copyright=!negative&&/(copyright|版权|著作权|авторск|derechos de autor|저작권)/i.test(text);
    const blocked=/(blocked|禁播|屏蔽|заблокир|bloquead)/i.test(text);
    if(copyright)return blocked?'版权问题及禁播标识':'版权声明/版权问题';
    if(blocked)return '禁播（版权原因待核对）';
    return undefined;
  }
  function visibility(text){
    text=String(text||'').replace(/\s+/g,' ').trim();
    if(/(scheduled|定时|已安排|预定发布|排定|запланирован|programad|예약)/i.test(text))return 'scheduled';
    if(/(unlisted|不公开|非公开|не в списке|по ссылке|no listado|일부 공개)/i.test(text))return 'unlisted';
    if(/(private|私密|私享|私人|ограниченный доступ|privad|비공개)/i.test(text))return 'private';
    if(/(\bpublic\b|公开|общий доступ|públic|공개)/i.test(text))return 'public';
    return 'unknown';
  }
  globalThis.StudioCopyright={workbook,classify,visibility};
})();
