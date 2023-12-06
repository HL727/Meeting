<template>
    <v-card :loading="!object.id">
        <v-card-title><translate>EWS-koppling</translate></v-card-title>
        <v-card-text>
            <ErrorMessage :error="error || object.last_sync_error" />

            <h3><translate>Instruktioner</translate></h3>
            <ol>
                <li><translate>Logga in på Office 365 &gt; Admin. Gå till Azure Active Directory</translate></li>
                <li>
                    <translate>Välj App registrations</translate>
                    [<a
                        target="_blank"
                        href="https://aad.portal.azure.com/#blade/Microsoft_AAD_IAM/ActiveDirectoryMenuBlade/RegisteredApps"
                    ><translate>Länk</translate></a>]
                </li>
                <li><translate>Hitta och gå in på din app. ID är</translate> {{ oauth.client_id }}</li>
                <li>
                    <translate>Om du inte redan fyllt i Redirect URI i tidigare steg:</translate> &nbsp;
                    <translate>Gå in på Authentication. Tryck på Add platform och välj Web. Ange adressen nedan</translate>
                    <div style="max-width:600px;">
                        <ClipboardInput
                            solo
                            :value="oauth.callback_url"
                        />
                    </div>
                </li>
            </ol>

            <v-tabs>
                <v-tab><translate>Välj typ av inloggning</translate>: </v-tab>
                <v-tab-item>
                    <div class="pa-4">
                        <h3 v-translate>
                            Application permission
                        </h3>

                        <ul>
                            <li v-translate>
                                Kräver inte att Service Account kan logga in som sig själv
                            </li>
                        </ul>
                        <h3 v-translate>
                            Impersonation
                        </h3>
                        <ul>
                            <li v-translate>
                                Inloggning via ett befintligt konto i Office 365
                            </li>
                            <li v-translate>
                                Kalenderrättigheter utifrån åtkomsträttigheter för service account
                            </li>
                        </ul>
                        <p>
                            <translate>Läs ytterligare information hos Microsoft</translate>: <a href="https://docs.microsoft.com/en-us/exchange/client-developer/exchange-web-services/impersonation-and-ews-in-exchange">Impersonation and EWS in Exchange</a>
                        </p>
                    </div>
                </v-tab-item>

                <v-tab><translate>Application token</translate></v-tab>
                <v-tab-item>
                    <v-card flat>
                        <v-card-text>
                            <ol>
                                <li><translate>Gå till API permissions</translate></li>
                                <li><translate>Tryck lägg till. Välj fliken "APIs my organization uses", hitta "Office 365 Exchange Online". Välj Application</translate></li>
                                <li>
                                    <translate>Lägg till följande behörigheter</translate>
                                    <ul>
                                        <ul>
                                            <li><translate>Other / full_access_as_app</translate></li>
                                        </ul>
                                    </ul>
                                </li>
                                <li><translate>Tryck på 'Grant admin consent'</translate></li>
                            </ol>
                        </v-card-text>
                        <v-card-actions>
                            <v-btn
                                color="primary"
                                :disabled="!oauth.has_secret"
                                :href="`?app=1&customer=${$store.state.site.customerId}`"
                            >
                                <translate>Bekräfta inloggning</translate>
                            </v-btn>
                            <p v-if="!oauth.has_secret">
                                <i><translate>Application token kräver att man angett en secret</translate></i>
                            </p>
                        </v-card-actions>
                    </v-card>
                </v-tab-item>

                <v-tab><translate>Authorization / delegation</translate></v-tab>
                <v-tab-item>
                    <v-card flat>
                        <v-card-text>
                            <ol>
                                <li><translate>Gå till API permissions</translate></li>
                                <li><translate>Tryck lägg till. Välj fliken "APIs my organization uses", hitta "Office 365 Exchange Online". Välj Delegated</translate></li>
                                <li>
                                    <translate>Lägg till följande behörigheter</translate>
                                    <ul>
                                        <ul>
                                            <li><translate>EWS / EWS.AccessAsUser.All</translate></li>
                                        </ul>
                                    </ul>
                                </li>
                                <li><translate>Tryck på 'Grant admin consent'</translate></li>
                            </ol>
                        </v-card-text>
                        <v-card-actions>
                            <v-btn
                                color="primary"
                                :href="`?redirect=1&customer=${$store.state.site.customerId}`"
                            >
                                <translate>Verifiera inloggning</translate>
                            </v-btn>
                        </v-card-actions>
                    </v-card>
                </v-tab-item>
            </v-tabs>
        </v-card-text>
        <v-card-actions>
            <v-btn :to="{ name: 'cloud_dashboard_epm' }">
                <translate>Avbryt</translate>
            </v-btn>
        </v-card-actions>
    </v-card>
</template>


<script>
import ErrorMessage from '@/vue/components/base/ErrorMessage'
import ClipboardInput from '@/vue/components/ClipboardInput'

export default {
    components: {
        ClipboardInput,
        ErrorMessage,
    },
    props: {
        id: { type: Number, required: true }
    },
    data() {
        return {
            error: '',
        }
    },
    computed: {
        object() {
            const id = parseInt(this.id || 0)
            return Object.values(this.$store.state.provider.ewsCredentials).find(ews => ews.oauth_credential?.id === id) || {}
        },
        oauth() {
            return this.object.oauth_credential || {}
        }
    },
    mounted() {
        this.loadObject()
    },
    methods: {
        loadObject() {
            return this.$store.dispatch('provider/getExchangeCredentials')
        }
    }
}
</script>
