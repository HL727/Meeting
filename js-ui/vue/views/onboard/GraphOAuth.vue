<template>
    <v-card :loading="!object.id">
        <v-card-title><translate>MS Graph-koppling</translate></v-card-title>
        <v-card-text>
            <ErrorMessage :error="error || object.last_sync_error" />

            <h3><translate>Instruktioner</translate></h3>
            <ol>
                <li><translate>Om du har webbläsaren öppet från föregående steg, tryck på "Overview" i Azure och hoppa över denna lista</translate></li>
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
                    <translate>Om du inte redan angivit Redirect URI i föregående steg:</translate> &nbsp;
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
                                Kräver inte ett service account
                            </li>
                            <li v-translate>
                                Kräver att man manuellt lägger till API-behörigheter
                            </li>
                            <li v-translate>
                                Får automatiskt tillgång till alla rum och kräver inte att man manuellt tilldelar rättigheter som standard. Azure har kontroller för att ändra detta
                            </li>
                            <li v-translate>
                                För service providers som inte har fått tillgång till ett specifikt konto
                            </li>
                        </ul>
                        <h3>Delegation permission</h3>
                        <ul>
                            <li v-translate>
                                Inloggning via ett befintligt konto i Office 365
                            </li>
                            <li v-translate>
                                Kalenderrättigheter utifrån åtkomsträttigheter för service account
                            </li>
                        </ul>
                    </div>
                </v-tab-item>

                <v-tab><translate>Application token</translate></v-tab>
                <v-tab-item>
                    <v-card flat>
                        <v-card-text>
                            <ol>
                                <li><translate>Gå till API permissions</translate></li>
                                <li><translate>Tryck lägg till. Välj Microsoft Graph, stor ruta längst upp. Välj "Application permission"</translate></li>
                                <li>
                                    <translate>Lägg till följande behörigheter manuellt</translate> (Application permission)
                                    <ul>
                                        <ul>
                                            <li>Calendars.Read</li>
                                            <li>User.Read.All</li>
                                            <li>Place.Read.All</li>
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
                                <li>
                                    <translate>Lägg till behörigheter</translate>
                                    <ul>
                                        <li>
                                            <translate>Tryck på knappen för att godkänna behörigheter i Office 365:</translate>
                                            <v-btn
                                                class="ml-2"
                                                :href="`?consent=1&customer=${$store.state.site.customerId}`"
                                                small
                                            >
                                                <translate>godkänn</translate>
                                            </v-btn>
                                        </li>
                                        <li>
                                            <translate>Eller lägg till manuellt genom att gå till API permissions:</translate>
                                            <ul>
                                                <li>
                                                    <translate>Tryck Lägg till. Välj Microsoft Graph. Välj Delegated permission</translate>
                                                    <ul>
                                                        <li>Calendars.Read.Shared</li>
                                                        <li>User.ReadBasic.All</li>
                                                        <li>Place.Read.All</li>
                                                    </ul>
                                                </li>
                                                <li>
                                                    <translate>Tryck Grant admin consent</translate>
                                                </li>
                                            </ul>
                                        </li>
                                    </ul>
                                </li>
                            </ol>
                        </v-card-text>
                        <v-card-actions>
                            <v-btn
                                color="primary"
                                href="?redirect=1"
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
            return Object.values(this.$store.state.provider.msGraphCredentials).find(graph => graph.oauth_credential?.id === id) || {}
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
            return this.$store.dispatch('provider/getMSGraphCredentials')
        }
    }
}
</script>
