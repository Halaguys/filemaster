const $ = id => document.getElementById(id);
document.querySelectorAll('.tab').forEach(btn => btn.addEventListener('click', () => {
  document.querySelectorAll('.tab').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(c => c.classList.add('hidden'));
  btn.classList.add('active'); $(btn.dataset.tab).classList.remove('hidden');
}));
document.querySelectorAll('.dropzone').forEach(zone => {
  const input = $(zone.dataset.drop);
  input.addEventListener('change', () => {
    if(input.files.length) zone.querySelector('b').textContent = [...input.files].map(f=>f.name).join(', ');
  });
  ['dragenter','dragover'].forEach(e=>zone.addEventListener(e,ev=>{ev.preventDefault();zone.classList.add('drag')}));
  ['dragleave','drop'].forEach(e=>zone.addEventListener(e,ev=>{ev.preventDefault();zone.classList.remove('drag')}));
  zone.addEventListener('drop',ev=>{if(ev.dataTransfer.files.length){input.files=ev.dataTransfer.files;input.dispatchEvent(new Event('change'))}});
});
$('img-quality').addEventListener('input', e=>$('quality-value').textContent=e.target.value+'%');
async function postForm(url, form, statusId, filename) {
  const status=$(statusId); status.textContent='Processing…';
  try {
    const res=await fetch(url,{method:'POST',body:form});
    if(!res.ok){const d=await res.json().catch(()=>({detail:'Request failed'}));throw new Error(d.detail||'Request failed')}
    const blob=await res.blob(); const a=document.createElement('a'); a.href=URL.createObjectURL(blob);
    const cd=res.headers.get('content-disposition')||''; const match=cd.match(/filename="?([^";]+)"?/i);
    a.download=match?match[1]:filename; document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(a.href);
    status.textContent='Done — your file download has started.';
  } catch(e){status.textContent='Error: '+e.message}
}
function submitFile(url,id){const f=$(id).files[0];if(!f){$('pdf-status').textContent='Choose a PDF first.';return}const form=new FormData();form.append('file',f);postForm(url,form,'pdf-status','processed.pdf')}
function submitFiles(url,id){const fs=$(id).files;if(fs.length<2){$('pdf-status').textContent='Choose at least two PDF files.';return}const form=new FormData();[...fs].forEach(f=>form.append('files',f));postForm(url,form,'pdf-status','merged.pdf')}
function submitSplit(){const f=$('pdf-split-file').files[0];if(!f){$('pdf-status').textContent='Choose a PDF first.';return}const form=new FormData();form.append('file',f);form.append('pages',$('pdf-pages').value);postForm('/api/pdf/split',form,'pdf-status','split.pdf')}
function resizeImage(){const f=$('image-file').files[0];if(!f){$('image-status').textContent='Choose an image first.';return}const form=new FormData();form.append('file',f);form.append('width',$('img-width').value||0);form.append('height',$('img-height').value||0);form.append('quality',$('img-quality').value);form.append('max_kb',$('img-kb').value||0);form.append('output',$('img-format').value);postForm('/api/image/resize',form,'image-status','resized.jpg')}
function downloadMedia(){const url=$('media-url').value.trim();if(!url){$('media-status').textContent='Paste a media URL first.';return}const form=new FormData();form.append('url',url);form.append('kind',$('media-kind').value);form.append('quality',$('media-quality').value);postForm('/api/media/download',form,'media-status','filemaster-download')}
async function shortenLink(){const url=$('long-url').value.trim();const status=$('link-status');if(!url){status.textContent='Paste a URL first.';return}const form=new FormData();form.append('url',url);status.textContent='Creating short link…';try{const r=await fetch('/api/shorten',{method:'POST',body:form});const d=await r.json();if(!r.ok)throw new Error(d.detail);const full=location.origin+d.short_url;status.innerHTML='Your short link: <a target="_blank" rel="noopener" href="'+full+'">'+full+'</a> <button onclick="navigator.clipboard.writeText(\''+full+'\')">Copy</button>'}catch(e){status.textContent='Error: '+e.message}}
