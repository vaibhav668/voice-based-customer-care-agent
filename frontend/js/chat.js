import {
sendMessage
} from "./api.js";
import { langManager } from "./language.js";

document.addEventListener("DOMContentLoaded", () => {
    langManager.init("lang-selector-container");
});

const messages=

document.getElementById(

"messages"

);

const input=

document.getElementById(

"message"

);

const send=

document.getElementById(

"send"

);

function addMessage(sender,text){

messages.insertAdjacentHTML(

"beforeend",

`

<div>

<b>

${sender}

</b>

<p>

${text}

</p>

</div>

<hr>

`

);

messages.scrollTop=

messages.scrollHeight;

}

send.onclick=

async()=>{

const text=

input.value.trim();

if(!text)return;

addMessage(

"You",

text

);

input.value="";

try{

const response=

await sendMessage(text);

addMessage(

"Support AI",

response.response

);

}catch(err){

addMessage(

"Error",

err.message

);

}

};

input.addEventListener(

"keydown",

e=>{

if(e.key==="Enter")

send.click();

});