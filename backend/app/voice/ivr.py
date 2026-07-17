import enum
import uuid
import json
from typing import Dict, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database.models.user import User
from app.database.models.ivr_session import IvrSession
from app.repositories.conversation_repository import ConversationRepository
from app.voice.service import VoiceService
from app.websocket.routes import manager


class IVRState(str, enum.Enum):
    INCOMING = "INCOMING"
    RECORDING_CONSENT_PENDING = "RECORDING_CONSENT_PENDING"
    OTP_PENDING = "OTP_PENDING"
    LANGUAGE_SELECTION_PENDING = "LANGUAGE_SELECTION_PENDING"
    VERIFICATION_PENDING = "VERIFICATION_PENDING"
    VERIFICATION_PHONE_PENDING = "VERIFICATION_PHONE_PENDING"
    ACTIVE_AGENT = "ACTIVE_AGENT"
    FEEDBACK_PENDING = "FEEDBACK_PENDING"
    COMPLETED = "COMPLETED"


def broadcast_call_event(event_type: str, session_id: str, message: str, data: Optional[dict] = None):
    """Sends real-time WebSocket CRM notifications to all listening admin dashboards."""
    payload = {
        "event": event_type,
        "session_id": session_id,
        "message": message,
        "data": data or {},
    }
    manager.broadcast_sync(json.dumps(payload))


PROMPTS = {
    "en": {
        "ask_booking": "Please enter your booking reference code using your keypad.",
        "invalid_booking": "Invalid booking reference. Please enter your booking reference code again.",
        "unauthorized": "Sorry, you are not authorized to access information about another customer's booking.",
        "verified": "Thank you, reference verified. Please speak your support request now.",
        "choose_query": "If you want to ask another query, press 1. If your query is resolved, press 0.",
        "speak_query": "Please speak your query now.",
        "timeout_reminder": "We didn't receive any input. Press 1 to continue with another query, or 0 to finish.",
        "feedback": "Thank you. Please rate your support experience from 1 to 10 using your telephone keypad, where 0 represents a rating of 10.",
        "goodbye": "Thank you for calling. May you have a wonderful day ahead! Thank you."
    },
    "hi": {
        "ask_booking": "कृपया अपने कीपैड का उपयोग करके अपना बुकिंग संदर्भ कोड दर्ज करें।",
        "invalid_booking": "अमान्य बुकिंग संदर्भ। कृपया अपना बुकिंग संदर्भ कोड फिर से दर्ज करें।",
        "unauthorized": "क्षमा करें, आपको दूसरे ग्राहक की बुकिंग के बारे में जानकारी प्राप्त करने का अधिकार नहीं है।",
        "verified": "धन्यवाद, संदर्भ सत्यापित हो गया है। कृपया अब अपनी सहायता का अनुरोध बोलें।",
        "choose_query": "यदि आप दूसरा प्रश्न पूछना चाहते हैं, तो 1 दबाएं। यदि आपका प्रश्न हल हो गया है, तो 0 दबाएं।",
        "speak_query": "कृपया अब अपना प्रश्न बोलें।",
        "timeout_reminder": "हमें कोई इनपुट नहीं मिला। दूसरा प्रश्न पूछने के लिए 1 दबाएं, या समाप्त करने के लिए 0 दबाएं।",
        "feedback": "धन्यवाद। कृपया अपने सहायता अनुभव को 1 से 10 के पैमाने पर रेट करें, जहाँ 0 का अर्थ 10 है।",
        "goodbye": "कॉल करने के लिए धन्यवाद। आपका दिन शुभ हो! धन्यवाद।"
    },
    "te": {
        "ask_booking": "దయచేసి మీ కీప్యాడ్ ఉపయోగించి మీ బుకింగ్ రిఫరెన్స్ కోడ్‌ను నమోదు చేయండి.",
        "invalid_booking": "అవసరమైన బుకింగ్ రిఫరెన్స్ తప్పు. దయచేసి మీ బుకింగ్ రిఫరెన్స్ కోడ్‌ను మళ్లీ నమోదు చేయండి.",
        "unauthorized": "క్షమించండి, ఇతర కస్టమర్ యొక్క బుకింగ్ సమాచారాన్ని యాక్సెస్ చేయడానికి మీకు అనుమతి లేదు.",
        "verified": "ధన్యవాదాలు, రిఫరెన్స్ ధృవీకరించబడింది. దయచేసి మీ సహాయ అభ్యర్థనను ఇప్పుడు మాట్లాడండి.",
        "choose_query": "మీరు మరొక ప్రశ్న అడగాలనుకుంటే, 1 నొక్కండి. మీ ప్రశ్న పరిష్కరించబడితే, 0 నొక్కండి.",
        "speak_query": "దయచేసి మీ ప్రశ్నను ఇప్పుడు మాట్లాడండి.",
        "timeout_reminder": "మాకు ఎటువంటి ఇన్‌పుట్ అందలేదు. మరొక ప్రశ్న అడగడానికి 1 నొక్కండి, లేదా ముగించడానికి 0 నొక్కండి.",
        "feedback": "ధన్యవాదాలు. దయచేసి మీ టెలిఫోన్ కీప్యాడ్ ఉపయోగించి మీ సహాయ అనుభవాన్ని 1 నుండి 10 వరకు రేట్ చేయండి, ఇక్కడ 0 అంటే 10.",
        "goodbye": "కాల్ చేసినందుకు ధన్యవాదాలు. మీ రోజు బాగుండాలని కోరుకుంటున్నాము! ధన్యవాదాలు."
    },
    "ta": {
        "ask_booking": "தயவுசெய்து உங்கள் விசைப்பலகையைப் பயன்படுத்தி உங்கள் முன்பதிவு குறிப்பு குறியீட்டை உள்ளிடவும்.",
        "invalid_booking": "தவறான முன்பதிவு குறிப்பு. தயவுசெய்து உங்கள் முன்பதிவு குறிப்பு குறியீட்டை மீண்டும் உள்ளிடவும்.",
        "unauthorized": "மன்னிக்கவும், மற்றொரு வாடிக்கையாளரின் முன்பதிவு பற்றிய தகவலை அணுக உங்களுக்கு அனுமதி இல்லை.",
        "verified": "நன்றி, குறிப்பு சரிபார்க்கப்பட்டது. தயவுசெய்து உங்கள் ஆதரவு கோரிக்கையை இப்போது பேசவும்.",
        "choose_query": "நீங்கள் மற்றொரு கேள்வியைக் கேட்க விரும்பினால், 1 ஐ அழுத்தவும். உங்கள் கேள்வி தீர்க்கப்பட்டால், 0 ஐ அழுத்தவும்.",
        "speak_query": "தயவுசெய்து உங்கள் கேள்வியை இப்போது பேசவும்.",
        "timeout_reminder": "எந்த உள்ளீடும் பெறப்படவில்லை. மற்றொரு கேள்வியைத் தொடர 1 ஐ அழுத்தவும், அல்லது முடிக்க 0 ஐ அழுத்தவும்.",
        "feedback": "நன்றி. உங்கள் தொலைபேசி விசைப்பலகையைப் பயன்படுத்தி உங்கள் ஆதரவு அனுபவத்தை 1 முதல் 10 வரை மதிப்பிடவும், இதில் 0 என்பது 10 ஐக் குறிக்கிறது.",
        "goodbye": "அழைத்ததற்கு நன்றி. இந்த நாள் உங்களுக்கு இனிய நாளாக அமையட்டும்! நன்றி."
    },
    "mr": {
        "ask_booking": "कृपया आपल्या कीपॅडचा वापर करून आपला बुकिंग संदर्भ कोड प्रविष्ट करा.",
        "invalid_booking": "अवैध बुकिंग संदर्भ. कृपया आपला बुकिंग संदर्भ कोड पुन्हा प्रविष्ट करा.",
        "unauthorized": "क्षमस्व, आपल्याला दुसर्‍या ग्राहकाच्या बुकिंगबद्दलची माहिती मिळवण्याचा अधिकार नाही.",
        "verified": "धन्यवाद, संदर्भ सत्यापित केला गेला आहे. कृपया आता आपली मदत विनंती बोला.",
        "choose_query": "जर तुम्हाला दुसरा प्रश्न विचारायचा असेल तर 1 दाबा. जर तुमच्या प्रश्नाचे निवारण झाले असेल तर 0 दाबा.",
        "speak_query": "कृपया आपला प्रश्न आता बोला.",
        "timeout_reminder": "आम्हाला कोणताही इनपुट मिळाला नाही. दुसरा प्रश्न विचारण्यासाठी 1 दाबा, किंवा समाप्त करण्यासाठी 0 दाबा.",
        "feedback": "धन्यवाद. कृपया आपल्या टेलिफोन कीपॅडचा वापर करून आपल्या मदत अनुभवाचे 1 ते 10 च्या दरम्यान मूल्यांकन करा, जेथे 0 म्हणजे 10 आहे.",
        "goodbye": "कॉल केल्याबद्दल धन्यवाद. आपला आजचा दिवस चांगला जावो! धन्यवाद."
    },
    "kn": {
        "ask_booking": "ದಯವಿಟ್ಟು ನಿಮ್ಮ ಕೀಪ್ಯಾಡ್ ಬಳಸಿ ನಿಮ್ಮ ಬುಕಿಂಗ್ ಉಲ್ಲೇಖ ಕೋಡ್ ಅನ್ನು ನಮೂದಿಸಿ.",
        "invalid_booking": "ಅಮಾನ್ಯ ಬುಕಿಂಗ್ ಉಲ್ಲೇಖ. ದಯವಿಟ್ಟು ನಿಮ್ಮ ಬುಕಿಂಗ್ ಉಲ್ಲೇಖ ಕೋಡ್ ಅನ್ನು ಮತ್ತೆ ನಮೂದಿಸಿ.",
        "unauthorized": "ಕ್ಷಮಿಸಿ, ಇನ್ನೊಬ್ಬ ಗ್ರಾಹಕರ ಬುಕಿಂಗ್ ಬಗ್ಗೆ ಮಾಹಿತಿ ಪಡೆಯಲು ನಿಮಗೆ ಅಧಿಕಾರವಿಲ್ಲ.",
        "verified": "ಧನ್ಯವಾದಗಳು, ಉಲ್ಲೇಖವನ್ನು ಪರಿಶೀಲಿಸಲಾಗಿದೆ. ದಯವಿಟ್ಟು ನಿಮ್ಮ ಬೆಂಬಲ ವಿನಂತಿಯನ್ನು ಈಗ ಮಾತನಾಡಿ.",
        "choose_query": "ನೀವು ಇನ್ನೊಂದು ಪ್ರಶ್ನೆಯನ್ನು ಕೇಳಲು ಬಯಸಿದರೆ, 1 ಒತ್ತಿ. ನಿಮ್ಮ ಪ್ರಶ್ನೆ ಪರಿಹಾರವಾಗಿದ್ದರೆ, 0 ಒತ್ತಿ.",
        "speak_query": "ದಯವಿಟ್ಟು ನಿಮ್ಮ ಪ್ರಶ್ನೆಯನ್ನು ಈಗ ಮಾತನಾಡಿ.",
        "timeout_reminder": "ಯಾವುದೇ ಇನ್‌ಪುಟ್ ಸ್ವೀಕರಿಸಲಾಗಿಲ್ಲ. ಇನ್ನೊಂದು ಪ್ರಶ್ನೆಯನ್ನು ಕೇಳಲು 1 ಒತ್ತಿ, ಅಥವಾ ಮುಗಿಸಲು 0 ಒತ್ತಿ.",
        "feedback": "ಧನ್ಯವಾದಗಳು. ದಯವಿಟ್ಟು ನಿಮ್ಮ ದೂರವಾಣಿ ಕೀಪ್ಯಾಡ್ ಬಳಸಿ ನಿಮ್ಮ ಬೆಂಬಲ ಅನುಭವವನ್ನು 1 ರಿಂದ 10 ರವರೆಗೆ ರೇಟ್ ಮಾಡಿ, ಇಲ್ಲಿ 0 ಎಂದರೆ 10 ಆಗಿದೆ.",
        "goodbye": "ಕರೆ ಮಾಡಿದ್ದಕ್ಕಾಗಿ ಧನ್ಯವಾದಗಳು. ನಿಮ್ಮ ದಿನವು ಶುಭವಾಗಿರಲಿ! ಧನ್ಯವಾದಗಳು."
    },
    "gu": {
        "ask_booking": "કૃપા કરીને તમારા કીપેડનો ઉપયોગ કરીને તમારો બુકિંગ સંદર્ભ કોડ દાખલ કરો.",
        "invalid_booking": "અમાન્ય બુકિંગ સંદર્ભ. કૃપા કરીને તમારો બુકિંગ સંદર્ભ કોડ ફરીથી દાખલ કરો.",
        "unauthorized": "દિલગીર છીએ, તમને અન્ય ગ્રાહકના બુકિંગ વિશેની માહિતી મેળવવાની મંજૂરી નથી.",
        "verified": "આભાર, સંદર્ભ ચકાસવામાં આવ્યો છે. કૃપા કરીને હવે તમારી સપોર્ટ વિનંતી બોલો.",
        "choose_query": "જો તમે બીજો પ્રશ્ન પૂછવા માંગતા હો, તો 1 દબાવો. જો તમારો પ્રશ્ન હલ થઈ ગયો હોય, તો 0 દબાવો.",
        "speak_query": "કૃપા કરીને તમારો પ્રશ્ન હવે બોલો.",
        "timeout_reminder": "કોઈ ઇનપુટ મળ્યું નથી. બીજો પ્રશ્ન પૂછવા માટે 1 દબાવો, અથવા સમાપ્ત કરવા માટે 0 દબાવો.",
        "feedback": "આભાર. કૃпа કરીને તમારા ટેલિફોન કીપેડનો ઉપયોગ કરીને તમારા સપોર્ટ અનુભવને 1 થી 10 રેટ કરો, જ્યાં 0 એ 10 નું પ્રતિનિધિત્વ કરે છે.",
        "goodbye": "કૉલ કરવા બદલ આભાર. તમારો દિવસ સારો રહે! આભાર."
    },
    "bn": {
        "ask_booking": "অনুগ্রহ করে আপনার কিপ্যাড ব্যবহার করে আপনার বুকিং রেফারেন্স কোড লিখুন।",
        "invalid_booking": "অকার্যকর বুকিং রেফারেন্স। অনুগ্রহ করে আপনার বুকিং রেফারেন্স কোড আবার লিখুন।",
        "unauthorized": "দুঃখিত, অন্য গ্রাহকের বুকিং সম্পর্কিত তথ্য অ্যাক্সেস করার অনুমতি আপনার নেই।",
        "verified": "ধন্যবাদ, রেফারেন্স যাচাই করা হয়েছে। অনুগ্রহ করে এখন আপনার সহায়তার অনুরোধটি বলুন।",
        "choose_query": "আপনি যদি অন্য প্রশ্ন জিজ্ঞাসা করতে চান, তবে 1 টিপুন। আপনার সমস্যার সমাধান হয়ে থাকলে 0 টিপুন।",
        "speak_query": "অনুগ্রহ করে আপনার প্রশ্নটি এখন বলুন।",
        "timeout_reminder": "কোন ইনপুট পাওয়া যায়নি। অন্য প্রশ্ন জিজ্ঞাসা করতে 1 টিপুন, অথবা শেষ করতে 0 টিপুন।",
        "feedback": "ধন্যবাদ। অনুগ্রহ করে আপনার টেলিফোন কিপ্যাড ব্যবহার করে আপনার সহায়তার অভিজ্ঞতাকে 1 থেকে 10 এর মধ্যে রেট করুন, যেখানে 0 মানে 10 রেটিং।",
        "goodbye": "কল করার জন্য ধন্যবাদ। আপনার দিনটি শুভ হোক! ধন্যবাদ।"
    },
    "ml": {
        "ask_booking": "ദയവായി നിങ്ങളുടെ കീപാഡ് ഉപയോഗിച്ച് നിങ്ങളുടെ ബുക്കിംഗ് റഫറൻസ് കോഡ് നൽകുക.",
        "invalid_booking": "അസാധുവായ ബുക്കിംഗ് റഫറൻസ്. ദയവായി നിങ്ങളുടെ ബുക്കിംഗ് റഫറൻസ് കോഡ് വീണ്ടും നൽകുക.",
        "unauthorized": "ക്ഷമിക്കണം, മറ്റൊരു ഉപഭോക്താവിന്റെ ബുക്കിംഗ് വിവരങ്ങൾ ആക്സസ് ചെയ്യാൻ നിങ്ങൾക്ക് അനുമതിയില്ല.",
        "verified": "നന്ദി, റഫറൻസ് പരിശോധിച്ചു. ദയവായി നിങ്ങളുടെ പിന്തുണാ അഭ്യർത്ഥന ഇപ്പോൾ സംസാരിക്കുക.",
        "choose_query": "നിങ്ങൾക്ക് മറ്റൊരു ചോദ്യം ചോദിക്കണമെങ്കിൽ, 1 അമർത്തുക. നിങ്ങളുടെ ചോദ്യം പരിഹരിക്കപ്പെട്ടെങ്കിൽ, 0 അമർത്തുക.",
        "speak_query": "ദയവായി നിങ്ങളുടെ ചോദ്യം ഇപ്പോൾ സംസാരിക്കുക.",
        "timeout_reminder": "ഇൻപുട്ടുകളൊന്നും ലഭിച്ചില്ല. മറ്റൊരു ചോദ്യം ചോദിക്കാൻ 1 അമർത്തുക, അല്ലെങ്കിൽ പൂർത്തിയാക്കാൻ 0 അമർത്തുക.",
        "feedback": "നന്ദി. ദയവായി നിങ്ങളുടെ ടെലിഫോൺ കീപാഡ് ഉപയോഗിച്ച് നിങ്ങളുടെ പിന്തുണാ അനുഭവത്തെ 1 മുതൽ 10 വരെ വിലയിരുത്തുക, ഇവിടെ 0 എന്നാൽ 10 ആണ്.",
        "goodbye": "വിളിച്ചതിന് നന്ദി. നിങ്ങൾക്ക് ഒരു നല്ല ദിവസം ആശംസിക്കുന്നു! നന്ദി."
    },
    "ur": {
        "ask_booking": "براہ کرم اپنے کیپیڈ کا استعمال کرتے ہوئے اپنا بکنگ ریفرنس کوڈ درج کریں۔",
        "invalid_booking": "غلط بکنگ ریفرنس۔ براہ کرم اپنا بکنگ ریفرنس کوڈ دوبارہ درج کریں۔",
        "unauthorized": "معذرت، آپ کو دوسرے کسٹمر की बुकिंग के बारे में जानकारी प्राप्त करने की इजाजत नहीं है।",
        "verified": "شکریہ، ریفرنس کی تصدیق ہو گئی ہے۔ براہ کرم اب اپنی سپورٹ کی درخواست بولیں۔",
        "choose_query": "اگر آپ کوئی اور سوال پوچھنا چاہتے ہیں تو 1 دبائیں۔ اگر آپ کا سوال حل ہو گیا ہے तो 0 دبائیں۔",
        "speak_query": "براہ کرم اپنا سوال اب بولیں۔",
        "timeout_reminder": "ہمیں کوئی ان پٹ موصول نہیں ہوا۔ کوئی اور سوال پوچھنے کے لیے 1 دبائیں، یا ختم کرنے کے لیے 0 دبائیں۔",
        "feedback": "شکریہ۔ براہ کرم اپنے ٹیلی فون کیپیڈ کا استعمال کرتے ہوئے اپنے سپورٹ کے تجربے کو 1 سے 10 تک ریٹ کریں، جہاں 0 کا مطلب 10 ہے۔",
        "goodbye": "کال کرنے کے لیے شکریہ۔ آپ کا دن اچھا گزرے! شکریہ۔"
    }
}

# Override corrupted translated prompt literals above with clean phone-safe text.
PROMPTS.update({
    "hi": {
        "ask_booking": "कृपया अपने कीपैड से अपना बुकिंग रेफरेंस कोड दर्ज करें।",
        "invalid_booking": "बुकिंग रेफरेंस गलत है। कृपया कोड फिर से दर्ज करें।",
        "unauthorized": "माफ कीजिए, यह बुकिंग इस फोन नंबर से सत्यापित नहीं हो पाई।",
        "verified": "धन्यवाद, आपका रेफरेंस सत्यापित हो गया है। अब कृपया अपनी सहायता संबंधी बात बोलिए।",
        "choose_query": "दूसरा सवाल पूछने के लिए 1 दबाएं। अगर आपकी समस्या हल हो गई है, तो 0 दबाएं।",
        "speak_query": "कृपया अब अपना सवाल बोलिए।",
        "timeout_reminder": "हमें कोई जवाब नहीं मिला। दूसरा सवाल पूछने के लिए 1 दबाएं, या समाप्त करने के लिए 0 दबाएं।",
        "feedback": "धन्यवाद। कृपया अपने सहायता अनुभव को 1 से 10 तक रेट करें। 0 का मतलब 10 है।",
        "goodbye": "कॉल करने के लिए धन्यवाद। आपका दिन शुभ हो।",
    },
    "mr": {
        "ask_booking": "कृपया आपल्या कीपॅडवरून आपला बुकिंग रेफरन्स कोड प्रविष्ट करा.",
        "invalid_booking": "बुकिंग रेफरन्स चुकीचा आहे. कृपया कोड पुन्हा प्रविष्ट करा.",
        "unauthorized": "माफ करा, ही बुकिंग या फोन नंबरवरून सत्यापित झाली नाही.",
        "verified": "धन्यवाद, आपला रेफरन्स सत्यापित झाला आहे. कृपया आता आपला प्रश्न बोला.",
        "choose_query": "दुसरा प्रश्न विचारण्यासाठी 1 दाबा. समस्या सुटली असल्यास 0 दाबा.",
        "speak_query": "कृपया आता आपला प्रश्न बोला.",
        "timeout_reminder": "आम्हाला कोणताही प्रतिसाद मिळाला नाही. दुसरा प्रश्न विचारण्यासाठी 1 दाबा, किंवा समाप्त करण्यासाठी 0 दाबा.",
        "feedback": "धन्यवाद. कृपया आपल्या सपोर्ट अनुभवाला 1 ते 10 दरम्यान रेट करा. 0 म्हणजे 10.",
        "goodbye": "कॉल केल्याबद्दल धन्यवाद. आपला दिवस शुभ जावो.",
    },
    "te": {
        "ask_booking": "దయచేసి మీ కీప్యాడ్ ద్వారా మీ బుకింగ్ రిఫరెన్స్ కోడ్ నమోదు చేయండి.",
        "invalid_booking": "బుకింగ్ రిఫరెన్స్ తప్పుగా ఉంది. దయచేసి కోడ్ మళ్లీ నమోదు చేయండి.",
        "unauthorized": "క్షమించండి, ఈ ఫోన్ నంబర్ ద్వారా ఈ బుకింగ్ ధృవీకరించబడలేదు.",
        "verified": "ధన్యవాదాలు, మీ రిఫరెన్స్ ధృవీకరించబడింది. ఇప్పుడు మీ సహాయ అభ్యర్థనను చెప్పండి.",
        "choose_query": "మరొక ప్రశ్న అడగడానికి 1 నొక్కండి. మీ సమస్య పరిష్కారమైతే 0 నొక్కండి.",
        "speak_query": "దయచేసి ఇప్పుడు మీ ప్రశ్నను చెప్పండి.",
        "timeout_reminder": "మాకు ఎలాంటి ఇన్‌పుట్ రాలేదు. మరొక ప్రశ్నకు 1 నొక్కండి, ముగించడానికి 0 నొక్కండి.",
        "feedback": "ధన్యవాదాలు. మీ సహాయ అనుభవానికి 1 నుండి 10 వరకు రేటింగ్ ఇవ్వండి. 0 అంటే 10.",
        "goodbye": "కాల్ చేసినందుకు ధన్యవాదాలు. మీ రోజు శుభంగా ఉండాలి.",
    },
    "ta": {
        "ask_booking": "தயவுசெய்து உங்கள் கீபேடில் உங்கள் முன்பதிவு குறியீட்டை உள்ளிடவும்.",
        "invalid_booking": "முன்பதிவு குறியீடு தவறாக உள்ளது. தயவுசெய்து மீண்டும் உள்ளிடவும்.",
        "unauthorized": "மன்னிக்கவும், இந்த தொலைபேசி எண்ணால் இந்த முன்பதிவு சரிபார்க்கப்படவில்லை.",
        "verified": "நன்றி, உங்கள் குறியீடு சரிபார்க்கப்பட்டது. இப்போது உங்கள் கேள்வியை சொல்லுங்கள்.",
        "choose_query": "மற்றொரு கேள்விக்கு 1 அழுத்தவும். உங்கள் பிரச்சனை தீர்ந்துவிட்டால் 0 அழுத்தவும்.",
        "speak_query": "தயவுசெய்து இப்போது உங்கள் கேள்வியை சொல்லுங்கள்.",
        "timeout_reminder": "எந்த பதிலும் கிடைக்கவில்லை. மற்றொரு கேள்விக்கு 1 அழுத்தவும், முடிக்க 0 அழுத்தவும்.",
        "feedback": "நன்றி. உங்கள் ஆதரவு அனுபவத்தை 1 முதல் 10 வரை மதிப்பிடுங்கள். 0 என்பது 10.",
        "goodbye": "அழைத்ததற்கு நன்றி. உங்கள் நாள் இனிதாக அமையட்டும்.",
    },
    "kn": {
        "ask_booking": "ದಯವಿಟ್ಟು ನಿಮ್ಮ ಕೀಪ್ಯಾಡ್ ಬಳಸಿ ನಿಮ್ಮ ಬುಕಿಂಗ್ ರೆಫರೆನ್ಸ್ ಕೋಡ್ ನಮೂದಿಸಿ.",
        "invalid_booking": "ಬುಕಿಂಗ್ ರೆಫರೆನ್ಸ್ ತಪ್ಪಾಗಿದೆ. ದಯವಿಟ್ಟು ಕೋಡ್ ಅನ್ನು ಮತ್ತೆ ನಮೂದಿಸಿ.",
        "unauthorized": "ಕ್ಷಮಿಸಿ, ಈ ಫೋನ್ ಸಂಖ್ಯೆಯಿಂದ ಈ ಬುಕಿಂಗ್ ಪರಿಶೀಲನೆಯಾಗಲಿಲ್ಲ.",
        "verified": "ಧನ್ಯವಾದಗಳು, ನಿಮ್ಮ ರೆಫರೆನ್ಸ್ ಪರಿಶೀಲನೆಯಾಗಿದೆ. ಈಗ ನಿಮ್ಮ ಪ್ರಶ್ನೆಯನ್ನು ಹೇಳಿ.",
        "choose_query": "ಇನ್ನೊಂದು ಪ್ರಶ್ನೆ ಕೇಳಲು 1 ಒತ್ತಿರಿ. ಸಮಸ್ಯೆ ಪರಿಹಾರವಾದರೆ 0 ಒತ್ತಿರಿ.",
        "speak_query": "ದಯವಿಟ್ಟು ಈಗ ನಿಮ್ಮ ಪ್ರಶ್ನೆಯನ್ನು ಹೇಳಿ.",
        "timeout_reminder": "ನಮಗೆ ಯಾವುದೇ ಪ್ರತಿಕ್ರಿಯೆ ಸಿಕ್ಕಿಲ್ಲ. ಇನ್ನೊಂದು ಪ್ರಶ್ನೆಗೆ 1 ಒತ್ತಿರಿ, ಮುಗಿಸಲು 0 ಒತ್ತಿರಿ.",
        "feedback": "ಧನ್ಯವಾದಗಳು. ನಿಮ್ಮ ಸಹಾಯ ಅನುಭವಕ್ಕೆ 1 ರಿಂದ 10 ರವರೆಗೆ ರೇಟಿಂಗ್ ನೀಡಿ. 0 ಅಂದರೆ 10.",
        "goodbye": "ಕರೆ ಮಾಡಿದಕ್ಕಾಗಿ ಧನ್ಯವಾದಗಳು. ನಿಮ್ಮ ದಿನ ಶುಭವಾಗಿರಲಿ.",
    },
})
for _fallback_lang in ("gu", "bn", "ml", "ur"):
    PROMPTS[_fallback_lang] = PROMPTS.get("hi", PROMPTS["en"]).copy()


class IVRCallSession:

    def __init__(
        self,
        call_id: str,
        phone_number: str,
        db: Session,
    ):
        self.call_id = call_id
        self.phone_number = "".join(filter(str.isdigit, phone_number))[-10:] if phone_number else ""
        self.db = db
        
        self.state = IVRState.INCOMING
        self.recording_consent: Optional[bool] = None
        self.language: str = "en"
        self.user_id: Optional[str] = None
        self.session_id: str = f"ivr-{call_id}"
        self.booking_code: Optional[str] = None
        
        # Resolve caller identity securely
        self._identify_caller()

    def load_from_row(self, row: IvrSession):
        """Initializes state from database record."""
        self.call_id = row.call_id
        self.phone_number = row.phone_number
        self.state = IVRState(row.state)
        self.recording_consent = row.recording_consent
        self.language = row.language
        self.user_id = row.user_id
        self.session_id = row.session_id
        self.booking_code = row.booking_code

    def _save_to_db(self):
        """Persists the session details back to PostgreSQL/SQLite."""
        row = self.db.query(IvrSession).filter_by(call_id=self.call_id).first()
        if not row:
            row = IvrSession(call_id=self.call_id)
            self.db.add(row)
        
        row.phone_number = self.phone_number
        row.state = self.state.value
        row.recording_consent = self.recording_consent
        row.language = self.language
        row.user_id = self.user_id
        row.session_id = self.session_id
        row.booking_code = self.booking_code
        self.db.commit()

    def _log_system_event(self, message: str):
        """Logs a turn-by-turn system lifecycle event as a ConversationMessage."""
        conv_repo = ConversationRepository(self.db)
        conv = conv_repo.get_or_create_session(
            session_id=self.session_id,
            user_id=self.user_id,
            channel="VOICE",
            language=self.language,
        )
        
        # Insert SYSTEM sender conversation message log
        from app.repositories.conversation_message_repository import ConversationMessageRepository
        msg_repo = ConversationMessageRepository(self.db)
        msg_repo.add_message(
            conversation_id=conv.id,
            sender="SYSTEM",
            message_type="VOICE",
            message=message,
            booking_code=self.booking_code,
        )

    def _identify_caller(self):
        """Matches caller's phone number against registered users."""
        if not self.phone_number:
            return
        
        clean_caller = "".join(filter(str.isdigit, str(self.phone_number)))[-10:]
        if clean_caller:
            stmt = select(User).where(User.phone.like(f"%{clean_caller}%"))
            user = self.db.scalar(stmt)
            if user:
                self.user_id = str(user.id)
                self.language = user.preferred_language or "en"

    def _sync_verified_context(self):
        """Keeps DB-backed verification details available to the chat agent."""
        if self.booking_code:
            from app.repositories.booking_repository import BookingRepository

            booking = BookingRepository(self.db).get_booking_with_trip(self.booking_code)
            if booking:
                if not self.user_id and booking.user_id:
                    caller_digits = "".join(filter(str.isdigit, str(self.phone_number or "")))[-10:]
                    owner_digits = "".join(filter(str.isdigit, str(booking.user.phone if booking.user else "")))[-10:]
                    if caller_digits and caller_digits == owner_digits:
                        self.user_id = str(booking.user_id)
                        self._save_to_db()

                conv = ConversationRepository(self.db).get_or_create_session(
                    session_id=self.session_id,
                    user_id=self.user_id,
                    channel="VOICE",
                    language=self.language,
                )
                conv.booking_id = booking.id
                self.db.commit()

        from app.conversation.manager import ConversationManager

        mem_session = ConversationManager().get_session(self.session_id)
        mem_session.language = self.language
        if self.booking_code:
            mem_session.entities["booking_code"] = self.booking_code
        if self.phone_number:
            mem_session.entities["phone_number"] = self.phone_number
        if self.user_id:
            mem_session.entities["user_id"] = self.user_id

    def advance_state(self, action: str, data: Optional[str] = None) -> dict:
        """
        Processes IVR inputs (DTMF or voice) and transitions the call state.
        Returns the instructions (audio prompts and expected input types) for the IVR engine.
        """
        # Ensure database Conversation record exists immediately
        conv_repo = ConversationRepository(self.db)
        conv = conv_repo.get_or_create_session(
            session_id=self.session_id,
            user_id=self.user_id,
            channel="VOICE",
            language=self.language,
        )

        if self.state == IVRState.INCOMING:
            self.state = IVRState.LANGUAGE_SELECTION_PENDING
            self._save_to_db()
            self._log_system_event("Call incoming. Greeting caller and prompting for language selection.")
            broadcast_call_event("call_started", self.session_id, "Voice call started.", {"phone_number": self.phone_number})
            
            # Start call recording automatically (since manual consent prompt is removed)
            try:
                import plivo
                import os
                auth_id = os.getenv("PLIVO_AUTH_ID")
                auth_token = os.getenv("PLIVO_AUTH_TOKEN")
                public_url = os.getenv("PUBLIC_URL")
                auto_record = os.getenv("PLIVO_AUTO_RECORD", "false").lower() == "true"
                if auto_record and auth_id and auth_token and public_url:
                    client = plivo.RestClient(auth_id, auth_token)
                    recording = client.calls.start_recording(
                        call_uuid=self.call_id,
                        file_format='mp3',
                        callback_url=f"{public_url}/api/v1/telephony/plivo/recording-callback",
                    )
                    recording_id = getattr(recording, "recording_id", None) or (recording.get("recording_id") if hasattr(recording, "get") else None)
                    self._log_system_event(f"Call recording started automatically. Recording ID: {recording_id}")
            except Exception as e:
                self._log_system_event(f"Notice: Failed to start automatic call recording: {str(e)}")

            return {
                "state": self.state.value,
                "prompt": "Hi! Select your preferred language. Press 1 for English, 2 for Hindi, 3 for Telugu, 4 for Kannada, 5 for Marathi, 6 for Tamil, 7 for Gujarati, 8 for Bengali, 9 for Malayalam, or 0 for Urdu.",
                "expect_input": "DTMF",
                "num_digits": 1,
            }

        elif self.state == IVRState.RECORDING_CONSENT_PENDING:
            if action == "DTMF":
                if data == "1":
                    self.recording_consent = True
                    self._log_system_event("Recording consent accepted.")
                    # Trigger Plivo Call Recording dynamically
                    try:
                        import plivo
                        import os
                        auth_id = os.getenv("PLIVO_AUTH_ID")
                        auth_token = os.getenv("PLIVO_AUTH_TOKEN")
                        public_url = os.getenv("PUBLIC_URL")
                        auto_record = os.getenv("PLIVO_AUTO_RECORD", "false").lower() == "true"
                        if auto_record and auth_id and auth_token and public_url:
                            client = plivo.RestClient(auth_id, auth_token)
                            recording = client.calls.start_recording(
                                call_uuid=self.call_id,
                                file_format='mp3',
                                callback_url=f"{public_url}/api/v1/telephony/plivo/recording-callback",
                            )
                            recording_id = getattr(recording, "recording_id", None) or (recording.get("recording_id") if hasattr(recording, "get") else None)
                            self._log_system_event(f"Call recording started by system. Recording ID: {recording_id}")
                    except Exception as e:
                        self._log_system_event(f"Notice: Failed to start call recording: {str(e)}")
                else:
                    self.recording_consent = False
                    self._log_system_event("Recording consent rejected.")
                
                broadcast_call_event("call_updated", self.session_id, "Call recording consent updated.", {"recording_consent": self.recording_consent})

                # Check if phone number exists in database to pre-identify caller, but skip OTP flow completely
                user = None
                if self.phone_number:
                    clean_caller = "".join(filter(str.isdigit, str(self.phone_number)))[-10:]
                    if clean_caller:
                        stmt = select(User).where(User.phone.like(f"%{clean_caller}%"))
                        user = self.db.scalar(stmt)
                        if user:
                            self.user_id = str(user.id)

                self.state = IVRState.LANGUAGE_SELECTION_PENDING
                self._save_to_db()
                
                return {
                    "state": self.state.value,
                    "prompt": "Select your preferred language. Press 1 for English, 2 for Hindi, 3 for Telugu, 4 for Kannada, 5 for Marathi, 6 for Tamil, 7 for Gujarati, 8 for Bengali, 9 for Malayalam, or 0 for Urdu.",
                    "expect_input": "DTMF",
                    "num_digits": 1,
                }

        elif self.state == IVRState.OTP_PENDING:
            entered_otp = data.strip() if (action == "DTMF" and data) else ""
            user = None
            if self.phone_number:
                clean_caller = "".join(filter(str.isdigit, str(self.phone_number)))[-10:]
                if clean_caller:
                    stmt = select(User).where(User.phone.like(f"%{clean_caller}%"))
                    user = self.db.scalar(stmt)
            
            if user:
                from app.auth.service import verify_otp
                is_valid = verify_otp(user.phone, entered_otp)
                
                if is_valid:
                    self.user_id = str(user.id)
                    self.state = IVRState.LANGUAGE_SELECTION_PENDING
                    self._save_to_db()
                    
                    self._log_system_event(f"OTP verification successful for user {self.user_id}.")
                    broadcast_call_event("call_updated", self.session_id, "OTP verified successfully.", {"user_id": self.user_id})
                    
                    return {
                        "state": self.state.value,
                        "prompt": "OTP verification successful. Select your preferred language. Press 1 for English, 2 for Hindi, 3 for Telugu, 4 for Kannada, 5 for Marathi, 6 for Tamil, 7 for Gujarati, 8 for Bengali, 9 for Malayalam, or 0 for Urdu.",
                        "expect_input": "DTMF",
                        "num_digits": 1,
                    }
            
            self._log_system_event("OTP verification failed: incorrect OTP.")
            return {
                "state": self.state.value,
                "prompt": "Invalid OTP. Please enter the 6-digit OTP again using your keypad.",
                "expect_input": "DTMF",
                "num_digits": 6,
            }

        elif self.state == IVRState.LANGUAGE_SELECTION_PENDING:
            digit = data.strip() if (action == "DTMF" and data) else ""
            LANG_MAP = {
                "1": "en",
                "2": "hi",
                "3": "te",
                "4": "kn",
                "5": "mr",
                "6": "ta",
                "7": "gu",
                "8": "bn",
                "9": "ml",
                "0": "ur",
            }
            selected_lang = LANG_MAP.get(digit, "en")
            self.language = selected_lang
            self.state = IVRState.VERIFICATION_PENDING
            self._save_to_db()
            
            self._log_system_event(f"Language set to {self.language.upper()}.")
            conv.language = self.language
            self.db.commit()
            broadcast_call_event("call_updated", self.session_id, f"Language set to {self.language}.", {"language": self.language})
            
            prompt = PROMPTS.get(self.language, PROMPTS["en"])["ask_booking"]
            return {
                "state": self.state.value,
                "prompt": prompt,
                "expect_input": "DTMF",
            }

        elif self.state == IVRState.VERIFICATION_PENDING:
            booking_code = data.strip().upper() if (action == "DTMF" and data) else ""
            if booking_code:
                if not booking_code.startswith("BK-"):
                    booking_code = f"BK-{booking_code}"
                
                # Retrieve booking record from DB
                from app.repositories.booking_repository import BookingRepository
                booking_repo = BookingRepository(self.db)
                booking = booking_repo.get_booking_with_trip(booking_code)
                
                if not booking:
                    self._log_system_event(f"Caller verification failed: booking {booking_code} not found.")
                    prompt = PROMPTS.get(self.language, PROMPTS["en"])["invalid_booking"]
                    return {
                        "state": self.state.value,
                        "prompt": prompt,
                        "expect_input": "DTMF",
                    }
                
                # Check Booking Ownership
                if booking.user_id:
                    import uuid as _uuid
                    authorized = False
                    
                    # Primary: match by user_id (set after OTP verification)
                    if self.user_id:
                        try:
                            uid = _uuid.UUID(str(self.user_id))
                            booking_uid = _uuid.UUID(str(booking.user_id))
                            if uid == booking_uid:
                                authorized = True
                        except (ValueError, AttributeError):
                            pass
                    
                    # Fallback: match by caller phone number vs booking owner's phone
                    if not authorized and self.phone_number and booking.user:
                        caller_digits = "".join(filter(str.isdigit, str(self.phone_number)))[-10:]
                        owner_digits = "".join(filter(str.isdigit, str(booking.user.phone)))[-10:] if booking.user.phone else ""
                        if caller_digits and caller_digits == owner_digits:
                            authorized = True
                            # Also set user_id now that we know who this is
                            self.user_id = str(booking.user_id)
                            self._log_system_event(f"Caller authorized via phone number match for booking {booking_code}.")
                    
                    if not authorized:
                        self._log_system_event(f"Caller unauthorized for booking {booking_code}. Owned by different customer.")
                        prompt = PROMPTS.get(self.language, PROMPTS["en"])["unauthorized"]
                        return {
                            "state": self.state.value,
                            "prompt": prompt,
                            "expect_input": "DTMF",
                        }
                
                # Verified successfully!
                self.booking_code = booking_code
                self.state = IVRState.ACTIVE_AGENT
                self._save_to_db()
                
                import uuid as _uuid
                conv.booking_id = booking.id
                if self.user_id:
                    conv.user_id = _uuid.UUID(str(self.user_id)) if not isinstance(self.user_id, _uuid.UUID) else self.user_id
                self.db.commit()
                
                from app.conversation.manager import ConversationManager
                manager_inst = ConversationManager()
                session = manager_inst.get_session(self.session_id)
                session.language = self.language
                session.entities["booking_code"] = self.booking_code
                session.entities["phone_number"] = self.phone_number
                if self.user_id:
                    session.entities["user_id"] = self.user_id
                
                self._log_system_event(f"Booking {booking_code} verified. Entering active support agent.")
                broadcast_call_event("call_updated", self.session_id, f"Booking {booking_code} verified.", {
                    "state": "ACTIVE_AGENT",
                    "booking_code": self.booking_code,
                    "user_id": self.user_id,
                })
                
                prompt = PROMPTS.get(self.language, PROMPTS["en"])["verified"]
                return {
                    "state": self.state.value,
                    "prompt": prompt,
                    "expect_input": "VOICE",
                }
            else:
                prompt = PROMPTS.get(self.language, PROMPTS["en"])["ask_booking"]
                return {
                    "state": self.state.value,
                    "prompt": prompt,
                    "expect_input": "DTMF",
                }

        elif self.state == IVRState.VERIFICATION_PHONE_PENDING:
            self.state = IVRState.VERIFICATION_PENDING
            self._save_to_db()
            prompt = PROMPTS.get(self.language, PROMPTS["en"])["ask_booking"]
            return {
                "state": self.state.value,
                "prompt": prompt,
                "expect_input": "DTMF",
            }

        elif self.state == IVRState.ACTIVE_AGENT:
            return {
                "state": self.state.value,
                "prompt": "Active support session. Send voice input.",
                "expect_input": "VOICE",
            }

        elif self.state == IVRState.FEEDBACK_PENDING:
            rating = None
            if action == "DTMF" and data:
                digit = data.strip()
                if digit in ("0", "10"):
                    rating = 10
                elif digit.isdigit() and 1 <= int(digit) <= 9:
                    rating = int(digit)

            if rating is not None:
                from app.database.models.customer_feedback import CustomerFeedback
                fb = CustomerFeedback(
                    conversation_id=conv.id,
                    user_id=conv.user_id,
                    rating=rating,
                )
                self.db.add(fb)
                self.db.commit()
                self._log_system_event(f"Customer feedback rating received: {rating}.")
                broadcast_call_event("feedback_submitted", self.session_id, f"Customer submitted rating: {rating}", {
                    "rating": rating,
                    "phone_number": self.phone_number,
                })
            else:
                self._log_system_event("Customer feedback skipped or invalid.")

            self.state = IVRState.COMPLETED
            self._save_to_db()
            self.complete_call()
            
            prompt = PROMPTS.get(self.language, PROMPTS["en"])["goodbye"]
            return {
                "state": self.state.value,
                "prompt": prompt,
                "expect_input": "NONE",
            }

        return {
            "state": self.state.value,
            "prompt": "Thank you for calling. The call is completed.",
            "expect_input": "NONE",
        }

    async def process_voice_agent_turn(self, audio_path: str, audio_relative_path: Optional[str] = None) -> dict:
        """Processes voice turn: STT -> ChatAgent -> TTS."""
        if self.state != IVRState.ACTIVE_AGENT:
            return {"error": "Voice inputs are only allowed during the active agent state."}

        self._sync_verified_context()
        voice_service = VoiceService(db=self.db)
        
        # Process speech agent loop
        res = await voice_service.process(
            audio_path=audio_path,
            audio_relative_path=audio_relative_path,
            session_id=self.session_id,
            language=self.language,
            user_id=self.user_id,
            db=self.db,
        )

        # Retrieve resolution status updates
        conv = ConversationRepository(self.db).get_by_session_id(self.session_id)
        res_status = conv.resolution_status if conv else "unresolved"


        # Broadcast turn-by-turn transcripts and tool changes
        broadcast_call_event("new_transcript", self.session_id, f"Customer: {res.get('transcript')}", {
            "sender": "USER",
            "transcript": res.get("transcript"),
        })
        broadcast_call_event("new_transcript", self.session_id, f"AI: {res.get('text')}", {
            "sender": "AI",
            "transcript": res.get("text"),
        })
        
        # Broadcast status syncs
        if conv:
            broadcast_call_event("call_updated", self.session_id, f"Call state updated: {res_status}.", {
                "current_intent": conv.current_intent,
                "last_tool": conv.last_tool,
                "resolution_status": res_status,
            })

        return res

    async def process_text_agent_turn(self, text: str, append_text: str = "") -> dict:
        """Processes voice turn when transcription is already available (e.g. from Plivo Speech)."""
        if self.state != IVRState.ACTIVE_AGENT:
            return {"error": "Voice inputs are only allowed during the active agent state."}

        self._sync_verified_context()
        from app.schemas.chat import ChatRequest
        from app.services.chat_service import ChatService
        chat_service = ChatService(db=self.db)
        
        res_chat = chat_service.process(
            request=ChatRequest(
                session_id=self.session_id,
                message=text,
                language=self.language,
            ),
            user_id=self.user_id,
            channel="VOICE",
        )

        tts_text = res_chat["response"]
        if append_text:
            tts_text = f"{tts_text} {append_text}"

        # Bypass slow dynamic edge-tts generation to prevent Plivo webhook timeouts.
        # This will automatically fall back to Plivo's native, high-quality, zero-latency <Speak> tag.
        generated_audio = ""


        if res_chat.get("db_message_id"):
            try:
                from app.database.models.conversation_message import ConversationMessage
                db_msg = self.db.get(ConversationMessage, res_chat["db_message_id"])
                if db_msg:
                    db_msg.audio_path = generated_audio
                    self.db.commit()
            except Exception as e:
                print("Voice DB audio path sync notice:", e)

        res = {
            "session_id": res_chat["session_id"],
            "transcript": text,
            "text": res_chat["response"],
            "audio_path": generated_audio,
        }

        conv = ConversationRepository(self.db).get_by_session_id(self.session_id)
        res_status = conv.resolution_status if conv else "unresolved"


        broadcast_call_event("new_transcript", self.session_id, f"Customer: {text}", {
            "sender": "USER",
            "transcript": text,
        })
        broadcast_call_event("new_transcript", self.session_id, f"AI: {res.get('text')}", {
            "sender": "AI",
            "transcript": res.get('text'),
        })
        
        if conv:
            broadcast_call_event("call_updated", self.session_id, f"Call state updated: {res_status}.", {
                "current_intent": conv.current_intent,
                "last_tool": conv.last_tool,
                "resolution_status": res_status,
            })

        return res

    def complete_call(self) -> dict:
        """Gracefully completes the active call, setting ended_at and closing the DB conversation."""
        self.state = IVRState.COMPLETED
        self._save_to_db()

        conv = ConversationRepository(self.db).get_by_session_id(self.session_id)
        if conv:
            from app.database.models.conversation import ConversationStatus
            conv.status = ConversationStatus.CLOSED
            conv.ended_at = datetime.utcnow()
            self._log_system_event(f"Call disconnected/completed. Resolution: {conv.resolution_status}.")
            self.db.commit()

            broadcast_call_event("call_ended", self.session_id, "Call disconnected.", {
                "resolution_status": conv.resolution_status,
                "ended_at": conv.ended_at.isoformat()
            })

        return {
            "status": "completed",
            "message": "Call successfully ended.",
            "session_id": self.session_id,
        }


class IVRManager:
    """Database-backed IVR Call Session Store."""

    def __init__(self):
        self.calls: Dict[str, IVRCallSession] = {}

    def get_or_create_call(self, call_id: str, phone_number: str, db: Session) -> IVRCallSession:
        # Check local cache first
        if call_id in self.calls:
            self.calls[call_id].db = db
            return self.calls[call_id]

        # Check database persistence strategy
        row = db.query(IvrSession).filter_by(call_id=call_id).first()
        if row:
            session = IVRCallSession(call_id, phone_number, db)
            session.load_from_row(row)
            self.calls[call_id] = session
            return session

        # Otherwise create new session record
        session = IVRCallSession(call_id, phone_number, db)
        session._save_to_db()
        self.calls[call_id] = session
        return session


ivr_manager = IVRManager()
