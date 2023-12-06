// Anrop
// ========

/*
Data skickas som url-encodad POST/PUT-data, och returneras som JSON.

Parametrar (skickas via GET eller POST):
----------

Delad nyckel (obligatorisk):

    ?key=<shared key>

*/

desc = 'Ny bokning'
url = 'POST http://core.example.org/api/v1/meeting/'
url_alt = 'POST http://core.example.org/api/v1/meeting/book/'
args = meeting_request // se nedan
ret = meeting_response // se nedan

desc =
    'Bekräfta bokning, dvs när mötet faktiskt sparats i outlook. Annars kommer det rensas ut efter några timmar.'
url = 'POST http://core.example.org/api/v1/meeting/<id>/confirm/' // <id> ersätts med mötes-id
args = {}
ret = meeting_response // se nedan

desc = 'Ändra bokning. Ett nytt meeting_id kommer returneras'
url = 'PUT http://core.example.org/api/v1/meeting/<id>/' // <id> ersätts med mötes-id
url_alt = 'POST http://core.example.org/api/v1/meeting/update/<id>/' // <id> ersätts med mötes-id
args = meeting_request // se nedan

desc = 'Avboka'
url = 'DELETE http://core.example.org/api/v1/meeting/<id>/' // <id> ersätts med mötes-id
url_alt = 'POST http://core.example.org/api/v1/meeting/unbook/<id>/' // <id> ersätts med mötes-id
args = {}

desc = 'Hämta meddelande för möte'
url = 'GET http://core.example.org/api/v1/meeting/message/<id>/' // <id> ersätts med mötes-id
args = {}

desc = 'Hämta textsträngar'
url = 'GET http://core.example.org/api/v1/strings/'
args = {}
ret = {
    status: 'OK',
    welcome_title: 'Rubrik på hjälptext',
    welcome_message: 'HTML-innehåll för hjälptext',
    // ytterligare strängar som måste läggas till
}

desc = 'Kolla anslutning'
url = 'GET http://core.example.org/api/v1/status/'
args = {}
ret = {
    status: 'OK',
    enable_dialout: false,
}

// Anropsspecifikation
// ====================

meeting_request = {
    // delad nyckel för kunden
    key: 'shared_key',
    // användarnamn eller e-post etc för att kunna identifiera vem som gjort bokning (för historik/felsökning)
    creator: 'john',
    // Rubrik på möte (standard [kundnamn] + " möte")
    title: '',
    // om det är ett internt möte, dvs inte tillåter externa/mobila deltagare
    only_internal: false,
    // antalet fasta deltagare/mötesrum
    internal_clients: 1,
    // antalet externa deltagare
    external_clients: 3,
    // ev. pinkod (endast siffror). slumpgenerering bör göras av anroparen ifall det är aktuellt
    password: '',
    // tidpunkt för start i UTC. Format (utan mellanslag): YYYY MM DD 'T' HH mm ss 'Z'
    ts_start: '20140820T063000Z',
    // tidpunkt för stop i UTC. Format (utan mellanslag): YYYY MM DD 'T' HH mm ss 'Z'
    ts_stop: '20140820T073500Z',
    // ifall det är en återkommande händelse. beskriv i text mha iCal recurring-format
    // enligt http://tools.ietf.org/html/rfc5545#section-3.3.10  Ex. FREQ=DAILY;COUNT=5;INTERVAL=10
    // Dialout och inspelning fungerar i nuläget inte för återkommande möten
    recurring: '',
    // undantag på återkommande händelser. Kommaseparerad sträng med datum enligt samma format som ts_start/ts_stop
    recurring_exceptions: '',
    // Systemkälla
    source: 'outlook',
    // Skärmlayout (endast acano)
    layout: 'allEqual|speakerOnly|telepresence|stacked',
    // Information om konferensrum. Sträng innehållandes JSON-encodad lista med objekt som innehåller information om mötesrum
    room_info: JSON.encode([{ title: 'Konferensrum 1', dialstring: '1.2.3.4##1234', dialout: true }]),
    // Övriga inställningar. Default false
    settings: JSON.encode({ force_encryption: true, disable_chat: true }),
    // Information om inspelning. Sträng innehållandes JSON-encodad lista med objekt som innehåller information om mötesrum
    recording: JSON.encode({ record: false, is_public: false, is_live: false, name: '' }),
    // markera mötet som bekräftat på en gång (behöver inte bekräftas med separat anrop)
    confirm: false,
}

// Resultatspecifikation
// ====================

meeting_response = {
    status: 'OK',
    meeting_id: '123-abc123', // uppdateras vid ändring
    // användarnamn eller e-post etc för att kunna identifiera vem som gjort bokning (för historik/felsökning)
    creator: 'john',
    // tidpunkt för start i UTC. Format (utan mellanslag): YYYY MM DD 'T' HH mm ss 'Z'
    ts_start: '20140820T063000Z',
    // tidpunkt för stop i UTC. Format (utan mellanslag): YYYY MM DD 'T' HH mm ss 'Z'
    ts_stop: '20140820T073500Z',
    // true eller false ifall värdet är återkommande
    is_recurring: false,
    rest_url: '/api/v1/meeting/<id>/', // rest-url för ett möte (Stöder GET/PUT/DELETE)
    // ifall det är en återkommande händelse. beskriv i text mha iCal recurring-format
    // enligt http://tools.ietf.org/html/rfc5545#section-3.3.10
    recurring: '',
    // antalet fasta mötesrum
    internal_clients: 1,
    // antalet externa klienter. Kan vara null ifall only_internal är true
    external_clients: 2,
    // om mötet bara tillåter fasta mötesrum
    only_internal: false,
    // ifall mötet bekräftats av videokonferenssystemet
    backend_active: false,
    // ifall mötet har PIN-kod
    has_password: false,
    // rumsnummer på konferensbryggan
    room_id: 1234,
    // rubrik för meddelande
    message_title: 'Anslut till mötet',
    // färdigformaterat invite-meddelande för mötet (?format=rtf eller ?format=html)
    message: '<h1>Ett möte</h1><p>...</p>',
    // url för att gå med i möte via webben. Lägg till &name=<namn> för att förifylla namnet
    web_url: 'http://mindspacecloud.com/index.html?id=12345',
    // uri att ringa upp via externt videosystem
    sip_uri: '1234@mindspacecloud.com',
}

// Felresultat
// ================
error_result = {
    status: 'Error',
    // Typ av fel. Någon av:
    // InvalidKey: Ogiltig kundnyckel
    // InvalidData: Ogiltig eller saknad data skickat till webbserver
    // ResponseError: Felmeddelande från videobryggan
    // Unhandled: Taskig kod av mig. :)
    type: 'ErrorType',
    message: 'Beskrivning av fel',
    fields: {}, // Endast InvalidData. Innehåller en lista på vilka fält som var felaktiga
}
