<template>
    <Page
        :title="$gettext('Demo generator')"
        icon="mdi-table-row-plus-after"
    >
        <template v-slot:search>
            <div class="d-flex align-center">
                <span
                    class="mr-2"
                    style="white-space: nowrap;"
                ><translate>Generera för</translate></span>
                <CustomerPicker
                    prepend-inner-icon="mdi-domain"
                    navigate
                    dense
                    :outlined="true"
                    hide-details
                />
            </div>
        </template>
        <template v-slot:content>
            <v-row>
                <v-col
                    lg="6"
                    xl="4"
                >
                    <v-card :loading="loading.calls">
                        <v-card-title>
                            <v-icon color="primary">
                                mdi-chart-line
                            </v-icon>
                            <translate>Samtalsstatistik</translate>
                        </v-card-title>
                        <v-divider />
                        <v-card-text>
                            <v-row>
                                <v-col cols="6">
                                    <v-select
                                        v-model="forms.calls.days"
                                        :items="[1, 2, 3, 4, 5, 6, 7, 14, 30]"
                                        :label="$gettext('Dagar tillbaka')"
                                    />
                                </v-col>
                                <v-col cols="6">
                                    <v-select
                                        v-model="forms.calls.calls"
                                        :items="[10, 20, 40, 100, 200]"
                                        :label="$gettext('Upp till # av samtal per dag')"
                                    />
                                </v-col>
                                <v-col cols="6">
                                    <v-select
                                        v-model="forms.calls.participants"
                                        :items="[2, 5, 10]"
                                        :label="$gettext('Deltagare upp till')"
                                        hide-details
                                    />
                                </v-col>
                                <v-col cols="12">
                                    <v-checkbox
                                        v-model="forms.calls.randomize_meeting_room"
                                        :label="$gettext('Slumpa mötesrum')"
                                        :hint="$gettext('Som standard kommer samtal läggas till standard mötesrum')"
                                        persistent-hint
                                    />
                                </v-col>
                                <v-col cols="12">
                                    <v-card :flat="!forms.calls.generate_for_endpoints">
                                        <v-card-text :class="{'pa-0': !forms.calls.generate_for_endpoints}">
                                            <v-checkbox
                                                v-model="forms.calls.generate_for_endpoints"
                                                :label="$gettext('Generera för rum system')"
                                            />
                                            <EndpointPicker
                                                v-if="forms.calls.generate_for_endpoints"
                                                v-model="forms.calls.endpoints"
                                                :button-text="$gettext('Alla system')"
                                            />
                                            <v-select
                                                v-if="forms.calls.generate_for_endpoints"
                                                v-model="forms.calls.endpoint_percent"
                                                :items="[10, 20, 50, 100]"
                                                :label="$gettext('Procent till system')"
                                                :hint="$gettext('Procent av deltagarna som ska vara system')"
                                                persistent-hint
                                            />
                                        </v-card-text>
                                    </v-card>
                                </v-col>
                            </v-row>
                        </v-card-text>
                        <v-expand-transition>
                            <v-card-text
                                v-if="results.calls"
                                class="grey lighten-4"
                            >
                                <v-card
                                    outlined
                                    class="mt-3"
                                >
                                    <v-card-text>
                                        <pre>{{ results.calls }}</pre>
                                    </v-card-text>
                                </v-card>
                            </v-card-text>
                        </v-expand-transition>
                        <v-divider />
                        <v-card-actions>
                            <v-btn
                                color="primary"
                                :disabled="isLoading"
                                :loading="loading.calls"
                                @click="generateCalls"
                            >
                                <translate>Generera</translate>
                            </v-btn>
                        </v-card-actions>
                    </v-card>
                </v-col>
                <v-col
                    lg="6"
                    xl="4"
                >
                    <v-card :loading="loading.peopleCount">
                        <v-card-title>
                            <v-icon color="primary">
                                mdi-account-group
                            </v-icon>
                            <translate>Personräknare</translate>
                        </v-card-title>
                        <v-divider />
                        <v-card-text>
                            <EndpointPicker
                                v-model="forms.peopleCount.endpoints"
                                :button-text="$gettext('Alla system')"
                            />
                            <v-select
                                v-model="forms.peopleCount.days"
                                :items="[1, 2, 3, 4, 5, 6, 7]"
                                :label="$gettext('Dagar tillbaka')"
                            />
                        </v-card-text>
                        <v-expand-transition>
                            <v-card-text
                                v-if="results.peopleCount"
                                class="grey lighten-4"
                            >
                                <v-card
                                    outlined
                                    class="mt-3"
                                >
                                    <v-card-text>
                                        <pre>{{ results.peopleCount }}</pre>
                                    </v-card-text>
                                </v-card>
                            </v-card-text>
                        </v-expand-transition>
                        <v-divider />
                        <v-card-actions>
                            <v-btn
                                color="primary"
                                :disabled="isLoading"
                                :loading="loading.peopleCount"
                                @click="generatePeopleCount"
                            >
                                <translate>Generera</translate>
                            </v-btn>
                        </v-card-actions>
                    </v-card>
                </v-col>
            </v-row>
            <v-row>
                <v-col
                    lg="6"
                    xl="4"
                >
                    <v-card
                        v-if="$store.state.site.enableEPM"
                        :loading="loading.endpoints"
                    >
                        <v-card-title>
                            <v-icon color="primary">
                                mdi-google-lens
                            </v-icon>
                            <translate>Fake videokonferenssystem</translate>
                        </v-card-title>
                        <v-divider />
                        <v-card-text>
                            <v-text-field
                                v-model.number="forms.endpoints.count"
                                :label="$gettext('Antal')"
                            />
                            <v-text-field
                                v-model.number="forms.endpoints.start_index"
                                :label="$gettext('Första räknare')"
                            />
                        </v-card-text>
                        <v-expand-transition>
                            <v-card-text
                                v-if="results.endpoints"
                                class="grey lighten-4"
                            >
                                <v-card
                                    outlined
                                    class="mt-3"
                                >
                                    <v-card-text>
                                        <pre>{{ results.endpoints }}</pre>
                                    </v-card-text>
                                </v-card>
                            </v-card-text>
                        </v-expand-transition>
                        <v-divider />
                        <v-card-actions>
                            <v-btn
                                color="primary"
                                :disabled="isLoading"
                                :loading="loading.endpoints"
                                @click="generateEndpoints"
                            >
                                <translate>Generera</translate>
                            </v-btn>
                        </v-card-actions>
                    </v-card>
                </v-col>
            </v-row>
        </template>
    </Page>
</template>

<script>
import Page from '@/vue/views/layout/Page'
import CustomerPicker from '@/vue/components/tenant/CustomerPicker'
import EndpointPicker from '@/vue/components/epm/endpoint/EndpointPicker'

export default {
    components: { Page, CustomerPicker, EndpointPicker },
    data() {
        return {
            loading: {
                calls: false,
                peopleCount: false,
                endpoints: false,
            },
            results: {},
            forms: {
                customer: null,
                calls: {
                    days: 2,
                    calls: 10,
                    participants: 5,
                    randomize_meeting_room: false,
                    generate_for_endpoints: false,
                    endpoints: null,
                    endpoint_percent: 10
                },
                peopleCount: {
                    days: 2,
                    endpoints: null
                },
                endpoints: {
                    count: 100,
                    start_index: 1,
                },
            }
        }
    },
    computed: {
        customerId() {
            return this.$store.state.site.customerId
        },
        isLoading() {
            return Object.values(this.loading).find(l => l === true)
        }
    },
    mounted() {
        this.forms.customer = this.$store.state.site.customers[this.$store.state.site.customerId]
    },
    methods: {
        generateCalls() {
            this.loading.calls = true
            this.results.calls = null

            return this.$store.api()
                .post('demo-generator/call_statistics/', {
                    ...this.forms.calls,
                    customer: this.customerId,
                    endpoints: this.forms.calls.endpoints || []
                })
                .then(response => {
                    this.results.calls = JSON.stringify(response, null, 2)
                    this.loading.calls = false
                })
                .catch(e => {
                    this.results.calls = JSON.stringify(e, null, 2)
                    this.loading.calls = false
                })
        },
        generatePeopleCount() {
            this.loading.peopleCount = true
            this.results.peopleCount = null

            return this.$store.api()
                .post('demo-generator/head_count/', {
                    ...this.forms.peopleCount,
                    customer: this.customerId,
                    endpoints: this.forms.peopleCount.endpoints || []
                })
                .then(response => {
                    this.results.peopleCount = JSON.stringify(response, null, 2)
                    this.loading.peopleCount = false
                })
                .catch(e => {
                    this.results.peopleCount = JSON.stringify(e, null, 2)
                    this.loading.peopleCount = false
                })
        },
        generateEndpoints() {
            const endpoints = []
            for (let i = this.forms.endpoints.start_index || 1; i < this.forms.endpoints.count; i++) {
                endpoints.push({
                    connection_type: 1,
                    hostname: `system${i}.endpointmock.dev.mividas.com`,
                })
            }
            this.loading.endpoints = true
            return this.$store.dispatch('endpoint/createEndpointBulk', endpoints).then(r => {
                this.loading.endpoints = false
                return r
            })
        }
    }
}
</script>
