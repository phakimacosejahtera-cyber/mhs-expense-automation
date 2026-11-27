const form=document.querySelector('#company-otp');
const send=document.querySelector('#send-code');
const entry=document.querySelector('#otp-entry');
const status=form.querySelector('[role=status]');
let busy=false;
async function login(verify){
  if(busy||!form.elements.email.reportValidity())return;
  busy=true;send.disabled=true;
  try{
    const response=await fetch('/api/auth/email/'+(verify?'verify':'start'),{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({email:form.elements.email.value,code:form.elements.code.value.trim()})
    });
    const data=await response.json();
    if(!response.ok)throw Error(data.detail||'Permintaan gagal.');
    if(verify){location.replace('/');return}
    entry.hidden=false;form.elements.code.required=true;
    status.textContent='Buka tautan pada email terbaru dengan browser yang digunakan untuk meminta email ini. Jika email berisi kode angka, masukkan di bawah.';

  }catch(error){status.textContent=error.message}
  finally{busy=false;send.disabled=false}
}
send.onclick=()=>login(false);
form.onsubmit=event=>{event.preventDefault();login(!entry.hidden)};
