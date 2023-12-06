from conferencecenter.tests.mock_data.response import FakeResponse

tms_requests = {
'POST GetPhonebooks': '''
<?xml version="1.0" encoding="utf-8"?>
  <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
      <soap:Body>
          <GetPhonebooksResponse xmlns="http://www.tandberg.net/2004/06/PhoneBookSearch/">
              <GetPhonebooksResult>
                  <Name />
                  <Id />
                  <Catalog>
                      <Name>.Katalog 1</Name>
                      <Id>c_51
                      </Id>
                      <Entry>
                          <Name>Entry nr 1</Name>
                          <Id>e_102348592
                          </Id>
                          <Route>
                              <CallType>Auto
                              </CallType>
                              <Protocol>H323
                              </Protocol>
                              <Restrict>Norestrict
                              </Restrict>
                              <DialString>1027347
                              </DialString>
                              <Description>1027347 (H.323)
                              </Description>
                              <SystemType />
                          </Route>
                          <IsLast>false
                          </IsLast>
                          <IsFirst>true
                          </IsFirst>
                          <BaseDN />
                          </Entry>
                     </Catalog>
                  <IsLast>false
                  </IsLast>
                  <IsFirst>false
                  </IsFirst>
                  <NoOfEntries>70
                  </NoOfEntries>
                  <FolderExists>true
                  </FolderExists>
              </GetPhonebooksResult>
          </GetPhonebooksResponse>
      </soap:Body>
  </soap:Envelope>
                      '''.strip(),
}


def tandberg_post(self, url, *args, **kwargs):

    method = kwargs.pop('method', '') or 'POST'

    for call, response in list(tms_requests.items()):

        if call in '%s %s' % (method, url):
            if isinstance(response, tuple):
                return FakeResponse(response[1], status_code=response[0])
            else:
                return FakeResponse(response)
    return FakeResponse('''{}''')