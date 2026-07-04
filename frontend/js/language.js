import { getSavedLanguage, saveLanguage, getToken } from "./storage.js";

export const TRANSLATIONS = {
    en: {
        // Nav & Header
        nav_home: "Home",
        nav_dashboard: "Dashboard",
        nav_chat: "AI Chat",
        nav_voice: "Voice Assistant",
        nav_bookings: "My Bookings",
        nav_trips: "Trip Status",
        nav_history: "Conversation History",
        history_title: "Conversation History",
        history_subtitle: "Permanent record of all text and voice support interactions",
        search_history_placeholder: "Search by booking code, intent, query...",
        all_channels: "All Channels",
        chat_channel: "Chat",
        voice_channel: "Voice",
        no_conversations: "No conversations found.",
        select_conversation_prompt: "Select a conversation from the left to view full chat history.",
        user_sender: "Customer",
        ai_sender: "SupportAI Assistant",
        intent_label: "Intent",
        tool_label: "Tool Used",
        time_label: "Time",
        response_time_label: "Response Time",
        nav_profile: "Profile",
        nav_login: "Login",
        nav_register: "Register",
        nav_logout: "Logout",
        app_title: "SupportAI",

        // Auth Pages
        login_title: "Welcome Back",
        login_subtitle: "Login to your SupportAI account",
        email_label: "Email Address",
        email_placeholder: "enter your email",
        password_label: "Password",
        password_placeholder: "enter your password",
        login_btn: "Sign In",
        no_account: "Don't have an account?",
        register_link: "Register here",

        register_title: "Create Account",
        register_subtitle: "Join SupportAI customer portal",
        fullname_label: "Full Name",
        fullname_placeholder: "enter your full name",
        phone_label: "Phone Number",
        phone_placeholder: "enter your phone number",
        register_btn: "Create Account",
        has_account: "Already have an account?",
        login_link: "Login here",

        // Dashboard
        dashboard_welcome: "Welcome to SupportAI Portal",
        dashboard_subtitle: "Manage your bus travel, live trip updates, and AI customer support.",
        card_chat_title: "Text Chat Support",
        card_chat_desc: "Ask questions about booking, delays, refunds, cancellations, and policies.",
        card_chat_btn: "Open Chat",
        card_voice_title: "Voice Assistant",
        card_voice_desc: "Speak naturally in your language to get instant voice support.",
        card_voice_btn: "Try Voice Support",
        card_booking_title: "Booking Lookup",
        card_booking_desc: "Check ticket status, seat details, and payment information.",
        card_booking_btn: "Find Booking",
        card_trips_title: "Live Trip Tracking",
        card_trips_desc: "Track bus status, delays, and departure/arrival times.",
        card_trips_btn: "View Trips",

        // Chat Page
        chat_title: "AI Support Chat",
        chat_subtitle: "Instant help for bus bookings, delays, and travel FAQs",
        chat_placeholder: "Type your message here...",
        send_btn: "Send",
        chat_welcome: "Hello! I am your SupportAI assistant. How can I help you today?",

        // Voice Page
        voice_title: "Multilingual Voice Support",
        voice_subtitle: "Record your voice or upload an audio file to speak with our AI agent",
        voice_start_record: "🎤 Start Recording",
        voice_stop_record: "⏹ Stop Recording",
        voice_upload_heading: "Or Upload Audio File",
        voice_upload_btn: "Upload & Process",
        voice_transcript: "🎤 Transcript",
        voice_response: "🤖 AI Response",
        voice_processing: "⏳ Processing your voice query...",

        // Booking & Trips Pages
        booking_search_title: "Find Your Booking",
        booking_code_label: "Booking Code",
        booking_code_placeholder: "e.g. BK-100001",
        search_btn: "Search",
        booking_details: "Booking Details",
        seat_label: "Seat Number",
        status_label: "Booking Status",
        payment_label: "Payment Status",
        departure_label: "Departure",
        arrival_label: "Arrival",
        origin_label: "Origin",
        destination_label: "Destination",

        // Profile Page
        profile_title: "User Profile",
        profile_subtitle: "Your personal account information and language preference",
        pref_lang_label: "Preferred Language",

        // Status & Alerts
        login_success: "Logged in successfully!",
        register_success: "Registration successful! Please login.",
        auth_error: "Authentication failed. Please check your credentials.",
        request_failed: "Request failed. Please try again.",
        select_audio: "Please select an audio file.",
        processing: "Processing...",
        language_changed: "Language changed successfully"
    },

    hi: {
        // Nav & Header
        nav_home: "मुख्य पृष्ठ",
        nav_dashboard: "डैशबोर्ड",
        nav_chat: "एआई चैट",
        nav_voice: "वॉइस असिस्टेंट",
        nav_bookings: "मेरी बुकिंग्स",
        nav_trips: "बस स्थिति",
        nav_profile: "प्रोफ़ाइल",
        nav_login: "लॉगिन",
        nav_register: "पंजीकरण",
        nav_logout: "लॉगआउट",
        app_title: "सपोर्ट एआई",

        // Auth Pages
        login_title: "पुनः स्वागत है",
        login_subtitle: "अपने सपोर्ट एआई खाते में लॉगिन करें",
        email_label: "ईमेल पता",
        email_placeholder: "अपना ईमेल दर्ज करें",
        password_label: "पासवर्ड",
        password_placeholder: "अपना पासवर्ड दर्ज करें",
        login_btn: "साइन इन करें",
        no_account: "खाता नहीं है?",
        register_link: "यहाँ पंजीकरण करें",

        register_title: "खाता बनाएं",
        register_subtitle: "सपोर्ट एआई ग्राहक पोर्टल में शामिल हों",
        fullname_label: "पूरा नाम",
        fullname_placeholder: "अपना पूरा नाम दर्ज करें",
        phone_label: "फोन नंबर",
        phone_placeholder: "अपना फोन नंबर दर्ज करें",
        register_btn: "खाता बनाएं",
        has_account: "पहले से खाता है?",
        login_link: "यहाँ लॉगिन करें",

        // Dashboard
        dashboard_welcome: "सपोर्ट एआई पोर्टल में आपका स्वागत है",
        dashboard_subtitle: "अपनी बस यात्रा, लाइव अपडेट और एआई सहायता प्रबंधित करें।",
        card_chat_title: "टेक्स्ट चैट सहायता",
        card_chat_desc: "बुकिंग, देरी, रिफंड और रद्दीकरण से जुड़े प्रश्न पूछें।",
        card_chat_btn: "चैट खोलें",
        card_voice_title: "वॉइस असिस्टेंट",
        card_voice_desc: "अपनी भाषा में बोलकर तुरंत वॉइस सहायता प्राप्त करें।",
        card_voice_btn: "वॉइस सहायता आज़माएं",
        card_booking_title: "बुकिंग खोजें",
        card_booking_desc: "टिकट की स्थिति, सीट विवरण और भुगतान की जानकारी देखें।",
        card_booking_btn: "बुकिंग खोजें",
        card_trips_title: "लाइव ट्रिप ट्रैकिंग",
        card_trips_desc: "बस की स्थिति, देरी और प्रस्थान समय की जांच करें।",
        card_trips_btn: "ट्रिप्स देखें",

        // Chat Page
        chat_title: "एआई सहायता चैट",
        chat_subtitle: "बस बुकिंग, देरी और प्रश्नों के लिए तुरंत सहायता",
        chat_placeholder: "अपना संदेश यहाँ टाइप करें...",
        send_btn: "भेजें",
        chat_welcome: "नमस्ते! मैं आपका सपोर्ट एआई सहायक हूँ। आज मैं आपकी क्या मदद कर सकता हूँ?",

        // Voice Page
        voice_title: "बहुभाषी वॉइस सहायता",
        voice_subtitle: "एआई एजेंट से बात करने के लिए अपनी आवाज़ रिकॉर्ड करें या ऑडियो फ़ाइल अपलोड करें",
        voice_start_record: "🎤 रिकॉर्डिंग शुरू करें",
        voice_stop_record: "⏹ रिकॉर्डिंग बंद करें",
        voice_upload_heading: "या ऑडियो फ़ाइल अपलोड करें",
        voice_upload_btn: "अपलोड और प्रोसेस करें",
        voice_transcript: "🎤 ट्रांसक्रिप्ट",
        voice_response: "🤖 एआई उत्तर",
        voice_processing: "⏳ आपकी वॉइस क्वेरी प्रोसेस की जा रही है...",

        // Booking & Trips Pages
        booking_search_title: "अपनी बुकिंग खोजें",
        booking_code_label: "बुकिंग कोड",
        booking_code_placeholder: "उदा. BK-100001",
        search_btn: "खोजें",
        booking_details: "बुकिंग विवरण",
        seat_label: "सीट संख्या",
        status_label: "बुकिंग स्थिति",
        payment_label: "भुगतान स्थिति",
        departure_label: "प्रस्थान",
        arrival_label: "आगमन",
        origin_label: "प्रारंभिक स्थान",
        destination_label: "गंतव्य",

        // Profile Page
        profile_title: "उपयोगकर्ता प्रोफ़ाइल",
        profile_subtitle: "आपकी व्यक्तिगत खाता जानकारी और भाषा प्राथमिकता",
        pref_lang_label: "पसंदीदा भाषा",

        // Status & Alerts
        login_success: "सफलतापूर्वक लॉगिन हुआ!",
        register_success: "पंजीकरण सफल! कृपया लॉगिन करें।",
        auth_error: "प्रमाणीकरण विफल। कृपया अपनी जानकारी जांचें।",
        request_failed: "अनुरोध विफल। कृपया पुनः प्रयास करें।",
        select_audio: "कृपया एक ऑडियो फ़ाइल चुनें।",
        processing: "प्रक्रिया जारी है...",
        language_changed: "भाषा सफलतापूर्वक बदली गई"
    },

    mr: {
        // Nav & Header
        nav_home: "मुख्य पृष्ठ",
        nav_dashboard: "डॅशबोर्ड",
        nav_chat: "एआय चॅट",
        nav_voice: "व्हॉइस असिस्टंट",
        nav_bookings: "माझ्या बुकिंग्स",
        nav_trips: "बस स्थिती",
        nav_profile: "प्रोफाइल",
        nav_login: "लॉगिन",
        nav_register: "नोंदणी",
        nav_logout: "लॉगआउट",
        app_title: "सपोर्ट एआय",

        // Auth Pages
        login_title: "पुन्हा स्वागत आहे",
        login_subtitle: "तुमच्या सपोर्ट एआय खात्यात लॉगिन करा",
        email_label: "ईमेल पत्ता",
        email_placeholder: "तुमचा ईमेल प्रविष्ट करा",
        password_label: "पासवर्ड",
        password_placeholder: "तुमचा पासवर्ड प्रविष्ट करा",
        login_btn: "साइन इन करा",
        no_account: "खाते नाही?",
        register_link: "येथे नोंदणी करा",

        register_title: "खाते तयार करा",
        register_subtitle: "सपोर्ट एआय ग्राहक पोर्टलवर सामील व्हा",
        fullname_label: "पूर्ण नाव",
        fullname_placeholder: "तुमचे पूर्ण नाव प्रविष्ट करा",
        phone_label: "फोन नंबर",
        phone_placeholder: "तुमचा फोन नंबर प्रविष्ट करा",
        register_btn: "खाते तयार करा",
        has_account: "आधीच खाते आहे?",
        login_link: "येथे लॉगिन करा",

        // Dashboard
        dashboard_welcome: "सपोर्ट एआय पोर्टलवर आपले स्वागत आहे",
        dashboard_subtitle: "तुमचा बस प्रवास, लाइव्ह अपडेट्स आणि एआय मदत व्यवस्थापित करा.",
        card_chat_title: "टेक्स्ट चॅट मदत",
        card_chat_desc: "बुकिंग, विलंब, परतावा आणि रद्द करण्याशी संबंधित प्रश्न विचारा.",
        card_chat_btn: "चॅट उघडा",
        card_voice_title: "व्हॉइस असिस्टंट",
        card_voice_desc: "तुमच्या भाषेत बोलून त्वरित व्हॉइस मदत मिळवा.",
        card_voice_btn: "व्हॉइस मदत वापरा",
        card_booking_title: "बुकिंग शोधा",
        card_booking_desc: "तिकीट स्थिती, सीट तपशील आणि पेमेंट माहिती तपासा.",
        card_booking_btn: "बुकिंग शोधा",
        card_trips_title: "लाइव्ह ट्रिप ट्रॅकिंग",
        card_trips_desc: "बस स्थिती, विलंब आणि सुटण्याची वेळ तपासा.",
        card_trips_btn: "ट्रिप्स पहा",

        // Chat Page
        chat_title: "एआय सपोर्ट चॅट",
        chat_subtitle: "बस बुकिंग, विलंब आणि प्रश्नांसाठी त्वरित मदत",
        chat_placeholder: "तुमचा संदेश येथे टाईप करा...",
        send_btn: "पाठवा",
        chat_welcome: "नमस्कार! मी तुमचा सपोर्ट एआय सहाय्यक आहे. मी तुम्हाला कशी मदत करू शकतो?",

        // Voice Page
        voice_title: "बहुभाषिक व्हॉइस सपोर्ट",
        voice_subtitle: "एआय एजंटशी बोलण्यासाठी तुमचा आवाज रेकॉर्ड करा किंवा ऑडिओ फाईल अपलोड करा",
        voice_start_record: "🎤 रेकॉर्डिंग सुरू करा",
        voice_stop_record: "⏹ रेकॉर्डिंग थांबवा",
        voice_upload_heading: "किंवा ऑडिओ फाईल अपलोड करा",
        voice_upload_btn: "अपलोड करा आणि प्रक्रिया करा",
        voice_transcript: "🎤 ट्रान्सक्रिप्ट",
        voice_response: "🤖 एआय उत्तर",
        voice_processing: "⏳ तुमच्या व्हॉइस प्रश्नावर प्रक्रिया होत आहे...",

        // Booking & Trips Pages
        booking_search_title: "तुमची बुकिंग शोधा",
        booking_code_label: "बुकिंग कोड",
        booking_code_placeholder: "उदा. BK-100001",
        search_btn: "शोधा",
        booking_details: "बुकिंग तपशील",
        seat_label: "सीट क्रमांक",
        status_label: "बुकिंग स्थिती",
        payment_label: "पेमेंट स्थिती",
        departure_label: "सुटण्याची वेळ",
        arrival_label: "पोहोचण्याची वेळ",
        origin_label: "प्रारंभिक ठिकाण",
        destination_label: "गंतव्यस्थान",

        // Profile Page
        profile_title: "वापरकर्ता प्रोफाइल",
        profile_subtitle: "तुमची वैयक्तिक खात्याची माहिती आणि भाषा पसंती",
        pref_lang_label: "पसंतीची भाषा",

        // Status & Alerts
        login_success: "यशस्वीपणे लॉगिन झाले!",
        register_success: "नोंदणी यशस्वी! कृपया लॉगिन करा.",
        auth_error: "प्रमाणीकरण अयशस्वी. कृपया तुमची माहिती तपासा.",
        request_failed: "विनंती अयशस्वी. कृपया पुन्हा प्रयत्न करा.",
        select_audio: "कृपया एक ऑडिओ फाईल निवडा.",
        processing: "प्रक्रिया सुरू आहे...",
        language_changed: "भाषा यशस्वीरित्या बदलली गेली"
    },

    te: {
        // Nav & Header
        nav_home: "హోమ్",
        nav_dashboard: "డాష్‌బోర్డ్",
        nav_chat: "AI చాట్",
        nav_voice: "వాయిస్ అసిస్టెంట్",
        nav_bookings: "నా బుకింగ్‌లు",
        nav_trips: "బస్సు స్థితి",
        nav_profile: "ప్రొఫైల్",
        nav_login: "లాగిన్",
        nav_register: "రిజిస్టర్",
        nav_logout: "లాగౌట్",
        app_title: "సపోర్ట్ AI",

        // Auth Pages
        login_title: "మళ్ళీ స్వాగతం",
        login_subtitle: "మీ సపోర్ట్ AI ఖాతాకు లాగిన్ చేయండి",
        email_label: "ఈమెయిల్ చిరునామా",
        email_placeholder: "మీ ఈమెయిల్ నమోదు చేయండి",
        password_label: "పాస్‌వర్డ్",
        password_placeholder: "మీ పాస్‌వర్డ్ నమోదు చేయండి",
        login_btn: "సైన్ ఇన్ చేయండి",
        no_account: "ఖాతా లేదా?",
        register_link: "ఇక్కడ రిజిస్టర్ చేయండి",

        register_title: "ఖాతాను సృష్టించండి",
        register_subtitle: "సపోర్ట్ AI కస్టమర్ పోర్టల్‌లో చేరండి",
        fullname_label: "పూర్తి పేరు",
        fullname_placeholder: "మీ పూర్తి పేరు నమోదు చేయండి",
        phone_label: "ఫోన్ నంబర్",
        phone_placeholder: "మీ ఫోన్ నంబర్ నమోదు చేయండి",
        register_btn: "ఖాతాను సృష్టించండి",
        has_account: "ఇప్పటికే ఖాతా ఉందా?",
        login_link: "ఇక్కడ లాగిన్ చేయండి",

        // Dashboard
        dashboard_welcome: "సపోర్ట్ AI పోర్టల్‌కు స్వాగతం",
        dashboard_subtitle: "మీ బస్సు ప్రయాణం, లైవ్ అప్‌డేట్‌లు మరియు AI సపోర్ట్‌ను నిర్వహించండి.",
        card_chat_title: "టెక్స్ట్ చాట్ సపోర్ట్",
        card_chat_desc: "బుకింగ్, జాప్యం, రీఫండ్ మరియు రద్దుల గురించి ప్రశ్నలు అడగండి.",
        card_chat_btn: "చాట్ ప్రారంభించండి",
        card_voice_title: "వాయిస్ అసిస్టెంట్",
        card_voice_desc: "మీ భాషలో మాట్లాడి తక్షణ వాయిస్ సపోర్ట్ పొందండి.",
        card_voice_btn: "వాయిస్ సపోర్ట్ చూడండి",
        card_booking_title: "బుకింగ్ వెతకండి",
        card_booking_desc: "టికెట్ స్థితి, సీటు వివరాలు మరియు చెల్లింపు వివరాలు చూడండి.",
        card_booking_btn: "బుకింగ్ వెతకండి",
        card_trips_title: "లైవ్ ట్రిప్ ట్రాకింగ్",
        card_trips_desc: "బస్సు స్థితి, ఆలస్యం మరియు బయలుదేరే సమయం చూడండి.",
        card_trips_btn: "ట్రిప్‌లను చూడండి",

        // Chat Page
        chat_title: "AI సపోర్ట్ చాట్",
        chat_subtitle: "బస్సు బుకింగ్‌లు మరియు ప్రశ్నలకు తక్షణ సహాయం",
        chat_placeholder: "మీ సందేశాన్ని ఇక్కడ టైప్ చేయండి...",
        send_btn: "పంపండి",
        chat_welcome: "నమస్కారం! నేను మీ సపోర్ట్ AI అసిస్టెంట్‌ని. ఈరోజు నేను మీకు ఎలా సహాయపడగలను?",

        // Voice Page
        voice_title: "బహుభాషా వాయిస్ సపోర్ట్",
        voice_subtitle: "AI ఏజెంట్‌తో మాట్లాడటానికి మీ వాయిస్‌ని రికార్డ్ చేయండి లేదా ఆడియో ఫైల్‌ని అప్‌లోడ్ చేయండి",
        voice_start_record: "🎤 రికార్డింగ్ ప్రారంభించండి",
        voice_stop_record: "⏹ రికార్డింగ్ ఆపండి",
        voice_upload_heading: "లేదా ఆడియో ఫైల్‌ని అప్‌లోడ్ చేయండి",
        voice_upload_btn: "అప్‌లోడ్ & ప్రాసెస్",
        voice_transcript: "🎤 ట్రాన్స్‌స్క్రిప్ట్",
        voice_response: "🤖 AI సమాధానం",
        voice_processing: "⏳ మీ వాయిస్ ప్రశ్న ప్రాసెస్ అవుతోంది...",

        // Booking & Trips Pages
        booking_search_title: "మీ బుకింగ్‌ని వెతకండి",
        booking_code_label: "బుకింగ్ కోడ్",
        booking_code_placeholder: "ఉదా. BK-100001",
        search_btn: "వెతకండి",
        booking_details: "బుకింగ్ వివరాలు",
        seat_label: "సీటు నంబర్",
        status_label: "బుకింగ్ స్థితి",
        payment_label: "చెల్లింపు స్థితి",
        departure_label: "బయలుదేరే సమయం",
        arrival_label: "చేరుకునే సమయం",
        origin_label: "ప్రారంభ స్థానం",
        destination_label: "గమ్యస్థానం",

        // Profile Page
        profile_title: "యూజర్ ప్రొఫైల్",
        profile_subtitle: "మీ వ్యక్తిగత ఖాతా సమాచారం మరియు భాషా ప్రాధాన్యత",
        pref_lang_label: "ఇష్టమైన భాష",

        // Status & Alerts
        login_success: "విజయవంతంగా లాగిన్ అయ్యారు!",
        register_success: "రిజిస్ట్రేషన్ పూర్తయింది! దయచేసి లాగిన్ చేయండి.",
        auth_error: "లాగిన్ విఫలమైంది. దయచేసి వివరాలను తనిఖీ చేయండి.",
        request_failed: "అభ్యర్థన విఫలమైంది. దయచేసి మళ్ళీ ప్రయత్నించండి.",
        select_audio: "దయచేసి ఆడియో ఫైల్‌ను ఎంచుకోండి.",
        processing: "ప్రాసెస్ అవుతోంది...",
        language_changed: "భాష విజయవంతంగా మార్చబడింది"
    },

    ta: {
        // Nav & Header
        nav_home: "முகப்பு",
        nav_dashboard: "டாஷ்போர்டு",
        nav_chat: "AI அரட்டை",
        nav_voice: "குரல் உதவியாளர்",
        nav_bookings: "என் முன்பதிவுகள்",
        nav_trips: "பேருந்து நிலை",
        nav_profile: "சுயவிவரம்",
        nav_login: "லॉगின்",
        nav_register: "பதிவு",
        nav_logout: "வெளியேறு",
        app_title: "சப்போர்ட் AI",

        // Auth Pages
        login_title: "மீண்டும் வருக",
        login_subtitle: "உங்கள் சப்போர்ட் AI கணக்கில் உள்நுழையவும்",
        email_label: "மின்னஞ்சல் முகவரி",
        email_placeholder: "உங்கள் மின்னஞ்சலை உள்ளிடவும்",
        password_label: "கடவுச்சொல்",
        password_placeholder: "உங்கள் கடவுச்சொல்லை உள்ளிடவும்",
        login_btn: "உள்நுழைக",
        no_account: "கணக்கு இல்லையா?",
        register_link: "இங்கே பதிவு செய்யவும்",

        register_title: "கணக்கை உருவாக்கவும்",
        register_subtitle: "சப்போர்ட் AI வாடிக்கையாளர் தளத்தில் இணையுங்கள்",
        fullname_label: "முழு பெயர்",
        fullname_placeholder: "உங்கள் முழு பெயரை உள்ளிடவும்",
        phone_label: "தொலைபேசி எண்",
        phone_placeholder: "உங்கள் தொலைபேசி எண்ணை உள்ளிடவும்",
        register_btn: "கணக்கை உருவாக்கு",
        has_account: "ஏற்கனவே கணக்கு உள்ளதா?",
        login_link: "இங்கே உள்நுழையவும்",

        // Dashboard
        dashboard_welcome: "சப்போர்ட் AI தளத்திற்கு வருக",
        dashboard_subtitle: "உங்கள் பேருந்து பயணம், நேரலை தகவல்கள் மற்றும் AI உதவியை நிர்வகிக்கவும்.",
        card_chat_title: "உரை அரட்டை உதவி",
        card_chat_desc: "முன்பதிவு, தாமதம், பணம் திரும்பப் பெறுதல் பற்றிய கேள்விகளைக் கேளுங்கள்.",
        card_chat_btn: "அரட்டையைத் திற",
        card_voice_title: "குரல் உதவியாளர்",
        card_voice_desc: "உங்கள் மொழியில் பேசி உடனுக்குடன் குரல் உதவி பெறுங்கள்.",
        card_voice_btn: "குரல் உதவியை முயற்சிக்கவும்",
        card_booking_title: "முன்பதிவைத் தேடுங்கள்",
        card_booking_desc: "டிக்கெட் நிலை, இருக்கை விவரங்கள் மற்றும் கட்டணத் தகவலைப் பாருங்கள்.",
        card_booking_btn: "முன்பதிவைத் தேடு",
        card_trips_title: "நேரலை பயணக் கண்காணிப்பு",
        card_trips_desc: "பேருந்து நிலை, தாமதம் மற்றும் புறப்படும் நேரத்தைப் பாருங்கள்.",
        card_trips_btn: "பயணங்களைப் பார்",

        // Chat Page
        chat_title: "AI ஆதரவு அரட்டை",
        chat_subtitle: "பேருந்து முன்பதிவு மற்றும் கேள்விகளுக்கு உடனடி உதவி",
        chat_placeholder: "உங்கள் செய்தியை இங்கே தட்டச்சு செய்க...",
        send_btn: "அனுப்பு",
        chat_welcome: "வணக்கம்! நான் உங்கள் சப்போர்ட் AI உதவியாளன். இன்று உங்களுக்கு எப்படி உதவட்டும்?",

        // Voice Page
        voice_title: "பல்மொழி குரல் உதவி",
        voice_subtitle: "AI முகவருடன் பேச உங்கள் குரலைப் பதிவு செய்யவும் அல்லது ஆடியோ கோப்பைப் பதிவேற்றவும்",
        voice_start_record: "🎤 பதிவைத் தொடங்கு",
        voice_stop_record: "⏹ பதிவை நிறுத்து",
        voice_upload_heading: "அல்லது ஆடியோ கோப்பைப் பதிவேற்றவும்",
        voice_upload_btn: "பதிவேற்று & செயல்படுத்து",
        voice_transcript: "🎤 உரை வடிவம்",
        voice_response: "🤖 AI பதில்",
        voice_processing: "⏳ உங்கள் குரல் கேள்வி செயல்படுத்தப்படுகிறது...",

        // Booking & Trips Pages
        booking_search_title: "உங்கள் முன்பதிவைத் தேடுங்கள்",
        booking_code_label: "முன்பதிவு குறியீடு",
        booking_code_placeholder: "எ.கா. BK-100001",
        search_btn: "தேடு",
        booking_details: "முன்பதிவு விவரங்கள்",
        seat_label: "இருக்கை எண்",
        status_label: "முன்பதிவு நிலை",
        payment_label: "கட்டண நிலை",
        departure_label: "புறப்படும் நேரம்",
        arrival_label: "சென்றடையும் நேரம்",
        origin_label: "புறப்படும் இடம்",
        destination_label: "சென்றடையும் இடம்",

        // Profile Page
        profile_title: "பயனர் சுயவிவரம்",
        profile_subtitle: "உங்கள் தனிப்பட்ட கணக்குத் தகவல் மற்றும் மொழி விருப்பம்",
        pref_lang_label: "விருப்பமான மொழி",

        // Status & Alerts
        login_success: "வெற்றிகரமாக உள்நுழைந்தீர்கள்!",
        register_success: "பதிவு வெற்றி! தயவுசெய்து உள்நுழையவும்.",
        auth_error: "உள்நுழைவு தோல்வி. விவரங்களைச் சரிபார்க்கவும்.",
        request_failed: "கோரிக்கை தோல்வியடைந்தது. மீண்டும் முயற்சிக்கவும்.",
        select_audio: "தயவுசெய்து ஒரு ஆடியோ கோப்பைத் தேர்ந்தெடுக்கவும்.",
        processing: "செயல்பாட்டில் உள்ளது...",
        language_changed: "மொழி வெற்றிகரமாக மாற்றப்பட்டது"
    }
};

export const LANGUAGES = [
    { code: "en", name: "English", flag: "🇬🇧" },
    { code: "hi", name: "हिन्दी", flag: "🇮🇳" },
    { code: "mr", name: "मराठी", flag: "🇮🇳" },
    { code: "te", name: "తెలుగు", flag: "🇮🇳" },
    { code: "ta", name: "தமிழ்", flag: "🇮🇳" },
];

class LanguageManager {
    constructor() {
        this.currentLang = getSavedLanguage();
    }

    getLanguage() {
        return this.currentLang || "en";
    }

    async setLanguage(langCode, updateBackend = true) {
        if (!TRANSLATIONS[langCode]) return;
        this.currentLang = langCode;
        saveLanguage(langCode);
        this.applyTranslations();

        // If user is authenticated, sync preferred language with backend DB
        if (updateBackend && getToken()) {
            try {
                await fetch("http://127.0.0.1:8000/api/v1/users/me/language", {
                    method: "PUT",
                    headers: {
                        "Content-Type": "application/json",
                        "Authorization": `Bearer ${getToken()}`
                    },
                    body: JSON.stringify({ preferred_language: langCode })
                });
            } catch (err) {
                console.warn("Failed to sync language with backend:", err);
            }
        }
    }

    getText(key) {
        const dict = TRANSLATIONS[this.currentLang] || TRANSLATIONS.en;
        return dict[key] || TRANSLATIONS.en[key] || key;
    }

    applyTranslations() {
        const dict = TRANSLATIONS[this.currentLang] || TRANSLATIONS.en;

        // Translate inner HTML/text content
        document.querySelectorAll("[data-i18n]").forEach(elem => {
            const key = elem.getAttribute("data-i18n");
            if (dict[key]) {
                elem.textContent = dict[key];
            }
        });

        // Translate placeholders
        document.querySelectorAll("[data-i18n-placeholder]").forEach(elem => {
            const key = elem.getAttribute("data-i18n-placeholder");
            if (dict[key]) {
                elem.placeholder = dict[key];
            }
        });

        // Translate titles/tooltips
        document.querySelectorAll("[data-i18n-title]").forEach(elem => {
            const key = elem.getAttribute("data-i18n-title");
            if (dict[key]) {
                elem.title = dict[key];
            }
        });
    }

    renderLanguageSelector(container) {
        if (!container) return;

        const current = LANGUAGES.find(l => l.code === this.currentLang) || LANGUAGES[0];

        container.innerHTML = `
            <div class="lang-selector-wrapper" style="position: relative; display: inline-block;">
                <button type="button" class="lang-selector-btn" id="lang-menu-btn" style="
                    display: flex;
                    align-items: center;
                    gap: 6px;
                    background: rgba(255, 255, 255, 0.12);
                    border: 1px solid rgba(255, 255, 255, 0.25);
                    color: inherit;
                    padding: 6px 12px;
                    border-radius: 20px;
                    cursor: pointer;
                    font-size: 14px;
                    font-weight: 500;
                    backdrop-filter: blur(10px);
                    transition: all 0.2s ease;
                ">
                    <span>🌐</span>
                    <span>${current.name}</span>
                    <span style="font-size: 10px;">▼</span>
                </button>
                <div class="lang-dropdown-menu" id="lang-dropdown" style="
                    display: none;
                    position: absolute;
                    right: 0;
                    top: 110%;
                    background: #1e293b;
                    color: #f8fafc;
                    border: 1px solid #334155;
                    border-radius: 12px;
                    box-shadow: 0 10px 25px rgba(0,0,0,0.5);
                    min-width: 150px;
                    z-index: 1000;
                    overflow: hidden;
                    padding: 4px 0;
                ">
                    ${LANGUAGES.map(lang => `
                        <div class="lang-option" data-lang="${lang.code}" style="
                            padding: 8px 16px;
                            cursor: pointer;
                            display: flex;
                            align-items: center;
                            justify-content: space-between;
                            font-size: 14px;
                            color: ${lang.code === this.currentLang ? '#38bdf8' : '#e2e8f0'};
                            background: ${lang.code === this.currentLang ? 'rgba(56, 189, 248, 0.1)' : 'transparent'};
                            transition: background 0.15s ease;
                        ">
                            <span>${lang.flag} ${lang.name}</span>
                            ${lang.code === this.currentLang ? '<span>✓</span>' : ''}
                        </div>
                    `).join('')}
                </div>
            </div>
        `;

        const btn = container.querySelector("#lang-menu-btn");
        const dropdown = container.querySelector("#lang-dropdown");

        if (btn && dropdown) {
            btn.addEventListener("click", (e) => {
                e.stopPropagation();
                dropdown.style.display = dropdown.style.display === "block" ? "none" : "block";
            });

            document.addEventListener("click", () => {
                dropdown.style.display = "none";
            });

            dropdown.querySelectorAll(".lang-option").forEach(opt => {
                opt.addEventListener("click", async (e) => {
                    const langCode = opt.getAttribute("data-lang");
                    await this.setLanguage(langCode, true);
                    this.renderLanguageSelector(container);
                });
            });
        }
    }

    init(selectorContainerId = "lang-selector-container") {
        this.applyTranslations();
        const container = document.getElementById(selectorContainerId);
        if (container) {
            this.renderLanguageSelector(container);
        }
    }
}

export const langManager = new LanguageManager();
