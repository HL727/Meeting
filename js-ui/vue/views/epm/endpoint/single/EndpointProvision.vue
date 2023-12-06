<template>
    <v-form :disabled="loading">
        <v-card
            :flat="!dialog"
            :max-width="1080"
        >
            <v-card-title v-if="dialog">
                <translate>Provisionera</translate>
                <v-spacer />
                <v-menu
                    v-if="multiple.length > 1"
                    offset-y
                >
                    <template v-slot:activator="{ on }">
                        <v-btn
                            rounded
                            depressed
                            v-on="on"
                        >
                            <translate :translate-params="{length: multiple.length}">
                                %{length} valda endpoints
                            </translate>
                        </v-btn>
                    </template>
                    <v-list>
                        <v-list-item
                            v-for="(item, index) in endpoints"
                            :key="index"
                        >
                            <v-list-item-title><EndpointStatus :endpoint="item" /> {{ item.title }}</v-list-item-title>
                        </v-list-item>
                    </v-list>
                </v-menu>
            </v-card-title>
            <v-divider v-if="dialog" />

            <v-alert
                v-if="!dialog && !loading"
                class="my-4"
                type="info"
            >
                <translate>Notera att inga ändringar skrivs till systemen förrän de skickas via den här funktionen eller från Configuration-fliken</translate>
            </v-alert>

            <v-card-text :class="{ 'pa-0': !dialog }">
                <v-progress-linear
                    v-if="loading"
                    indeterminate
                    color="primary"
                    class="my-6"
                />

                <!-- Configuration -->
                <v-checkbox
                    v-if="!form.configuration"
                    v-model="form.configuration"
                    :label="$gettext('Uppdatera inställningar')"
                />
                <v-card
                    v-if="form.configuration"
                    class="mb-5"
                    :loading="loading"
                >
                    <v-card-text>
                        <v-checkbox
                            v-model="form.configuration"
                            :label="$gettext('Uppdatera inställningar')"
                            class="mt-0"
                            hide-details
                        />
                    </v-card-text>
                    <v-tabs
                        v-if="form.configuration"
                        v-model="form.configurationTab"
                        background-color="grey lighten-4"
                    >
                        <v-tab key="template">
                            <translate>Från en mall</translate>
                        </v-tab>
                        <v-tab key="endpoint">
                            <translate>Från ett system</translate>
                        </v-tab>
                        <v-tab key="edit">
                            <translate>Redigera manuellt</translate>
                        </v-tab>
                        <v-tab
                            key="check"
                            :disabled="!activeConfiguration.length"
                        >
                            <translate>Granska</translate> ({{ activeConfiguration.length }})
                        </v-tab>
                    </v-tabs>
                    <v-tabs-items
                        v-if="form.configuration"
                        v-model="form.configurationTab"
                    >
                        <v-tab-item key="template">
                            <EndpointTemplateGrid
                                v-model="form.selectedConfigurationTemplates"
                                :templates="configurationTemplates"
                                :loading="loading"
                                hide-remove
                                disable-select
                            >
                                <template v-slot:actions="{ item }">
                                    <v-btn
                                        small
                                        :loading="loadingConfigurations"
                                        @click="loadConfigurationTemplate(item)"
                                    >
                                        <translate>Ladda</translate>
                                    </v-btn>
                                </template>
                            </EndpointTemplateGrid>
                        </v-tab-item>
                        <v-tab-item
                            key="endpoint"
                            class="px-4 pb-6"
                        >
                            <EndpointGrid
                                v-model="form.configurationEndpoint"
                                checkbox
                                single
                            >
                                <template v-slot:actions="{ endpoints }">
                                    <v-btn
                                        :disabled="!endpoints.length || endpointConfigurationLoading"
                                        :loading="endpointConfigurationLoading"
                                        color="primary"
                                        @click="loadEndpoint(endpoints[0])"
                                    >
                                        <translate>Ladda inställningar</translate>
                                    </v-btn>
                                </template>
                            </EndpointGrid>
                        </v-tab-item>
                        <v-tab-item key="edit">
                            <EndpointConfigurationForm
                                :id="id"
                                @loaded="loading = false"
                            />
                        </v-tab-item>

                        <v-dialog
                            :value="!!editSetting"
                            max-width="640"
                            @input="editSetting = null"
                        >
                            <v-card>
                                <v-card-title><translate>Redigera manuellt</translate></v-card-title>
                                <v-divider />
                                <v-card-text>
                                    <ConfigurationWrapper
                                        v-if="editSetting"
                                        :setting="editSetting.setting || editSetting"
                                    />
                                </v-card-text>
                                <v-divider />
                                <v-card-actions>
                                    <v-spacer />
                                    <v-btn
                                        v-close-dialog
                                        text
                                        color="red"
                                    >
                                        <translate>Stäng</translate>
                                        <v-icon
                                            right
                                            dark
                                        >
                                            mdi-close
                                        </v-icon>
                                    </v-btn>
                                </v-card-actions>
                            </v-card>
                        </v-dialog>

                        <v-tab-item key="check">
                            <v-card-text class="text-right">
                                <v-btn
                                    :disabled="!activeConfiguration.length"
                                    color="primary"
                                    @click="templateForm.templateDialog = true"
                                >
                                    <translate>Spara inställningar som mall</translate>
                                </v-btn>
                                <v-btn
                                    v-if="activeConfiguration.length"
                                    dark
                                    class="ml-4"
                                    color="error"
                                    @click="$store.commit('endpoint/clearActiveConfiguration'); templateForm.activeEndpoint = null; form.configurationTab = 0"
                                >
                                    <v-icon left>
                                        mdi-close
                                    </v-icon>
                                    <translate>Rensa</translate>
                                </v-btn>
                            </v-card-text>
                            <SaveTemplateDialog
                                v-model="templateForm.templateDialog"
                                :configuration="activeConfiguration"
                                :endpoint="templateForm.activeEndpoint || endpoint"
                                max-width="320"
                                @created="loadRelatedItems"
                            />
                            <v-simple-table>
                                <thead>
                                    <tr>
                                        <th v-translate>
                                            Inställning
                                        </th>
                                        <th v-translate>
                                            Värde
                                        </th>
                                        <th />
                                    </tr>
                                </thead>
                                <tbody>
                                    <tr
                                        v-for="config in activeConfiguration"
                                        :key="config.key"
                                    >
                                        <td>
                                            {{ config.path.join(' > ') }}
                                        </td>
                                        <td>
                                            <small>
                                                {{ config.value }}
                                            </small>
                                        </td>
                                        <td class="text-right">
                                            <v-btn
                                                icon
                                                @click="editSetting = config"
                                            >
                                                <v-icon>mdi-pencil</v-icon>
                                            </v-btn>
                                        </td>
                                    </tr>
                                </tbody>
                            </v-simple-table>
                        </v-tab-item>
                    </v-tabs-items>
                </v-card>

                <!-- Commands -->
                <v-checkbox
                    v-if="!form.commands && isCisco"
                    v-model="form.commands"
                    :label="$gettext('Kör egna kommandon')"
                />
                <v-card
                    v-if="form.commands && isCisco"
                    class="mb-5"
                    :loading="loading"
                >
                    <v-card-text>
                        <v-checkbox
                            v-model="form.commands"
                            :label="$gettext('Kör egna kommandon')"
                            class="mt-0"
                            hide-details
                        />
                    </v-card-text>
                    <v-tabs
                        v-if="form.commands"
                        v-model="form.commandsTab"
                        background-color="grey lighten-4"
                    >
                        <v-tab key="template">
                            <translate>Från en mall</translate>
                        </v-tab>
                        <v-tab
                            key="check"
                            :disabled="!commandQueue.length"
                        >
                            <translate>Granska</translate> ({{ commandQueue.length }})
                        </v-tab>
                    </v-tabs>
                    <v-tabs-items
                        v-if="form.commands"
                        v-model="form.commandsTab"
                    >
                        <v-tab-item key="template">
                            <EndpointTemplateGrid
                                v-model="form.selectedCommandTemplates"
                                :templates="commandTemplates"
                                :loading="loading"
                                hide-remove
                                disable-select
                            >
                                <template v-slot:actions="{ item }">
                                    <v-btn
                                        small
                                        :loading="loadingCommands"
                                        @click="loadCommandTemplate(item)"
                                    >
                                        <translate>Ladda</translate>
                                    </v-btn>
                                </template>
                            </EndpointTemplateGrid>
                        </v-tab-item>

                        <v-tab-item key="check">
                            <v-card-text>
                                <v-btn
                                    v-if="commandQueue.length"
                                    dark
                                    color="error"
                                    @click="$store.commit('endpoint/clearCommandQueue'); form.commandsTab = 0"
                                >
                                    <v-icon left>
                                        mdi-close
                                    </v-icon>
                                    <translate>Rensa</translate>
                                </v-btn>
                            </v-card-text>
                            <v-simple-table>
                                <thead>
                                    <tr>
                                        <th v-translate>
                                            Kommando
                                        </th>
                                        <th v-translate>
                                            Argument
                                        </th>
                                        <th />
                                    </tr>
                                </thead>
                                <tbody>
                                    <tr
                                        v-for="command in commandQueue"
                                        :key="command.key"
                                    >
                                        <td>
                                            {{ command.command.path.join(' ') }}
                                        </td>
                                        <td>
                                            <small>
                                                {{ command.arguments }}
                                            </small>
                                        </td>
                                        <td class="text-right" />
                                    </tr>
                                </tbody>
                            </v-simple-table>
                        </v-tab-item>
                    </v-tabs-items>
                </v-card>

                <v-row v-if="isCisco">
                    <v-col
                        cols="12"
                        md="6"
                    >
                        <v-checkbox
                            v-model="form.events"
                            :label="$gettext('Prenumerera på liveuppdateringar')"
                            persistent-hint
                            :hint="$gettext('Aktiverar så status i Rooms uppdateras direkt när ex. ett samtal startar och så samtalsdata skickas för att kunna bygga upp statistik')"
                        />
                    </v-col>
                    <v-col
                        v-if="!multiple.length"
                        class="pt-md-8 text-md-right"
                    >
                        <v-progress-circular
                            v-if="loading"
                            indeterminate
                            size="24"
                            color="grey lighten-2"
                        />
                        <template v-else-if="provisionStatus">
                            <p>
                                <v-chip
                                    small
                                    :color="provisionStatus.event ? 'success' : 'error'"
                                >
                                    {{ provisionStatus.event ? $gettext('Aktiv') : $gettext('Ej aktiv') }}
                                </v-chip>
                            </p>
                            <p v-if="endpoint.status && endpoint.status.ts_last_event">
                                <translate>Senast mottagna meddelande</translate>:
                                {{ endpoint.status.ts_last_event|since }}
                            </p>
                        </template>
                    </v-col>
                </v-row>

                <v-checkbox
                    v-if="!form.password"
                    v-model="form.password"
                    :disabled="endpoint.connection_type === 0 && multiple.length === 0"
                    :label="$gettext('Ändra lösenord')"
                />
                <v-card
                    v-if="form.password"
                    class="my-5"
                >
                    <v-card-text>
                        <v-checkbox
                            v-model="form.password"
                            :label="$gettext('Ändra lösenord')"
                            class="mt-0"
                            hide-details
                        />
                    </v-card-text>
                    <v-divider />
                    <v-card-text class="grey lighten-4">
                        <v-checkbox
                            v-model="form.useStandardPassword"
                            :label="$gettext('Använd standardlösenord')"
                        />
                        {{ '' /* TODO: passive requests does not run as "admin" so password change always fail. Fixable or should this be removed? */ }}
                        <v-text-field
                            v-if="endpoint.connection_type === 0 && !endpoint.has_password"
                            v-model="form.currentPassword"
                            :label="$gettext('Nuvarande lösenord')"
                        />
                        <v-text-field
                            v-if="!form.useStandardPassword"
                            v-model="form.newPassword"
                            :label="$gettext('Nytt lösenord')"
                            append-icon="mdi-refresh"
                            type="password"
                            :rules="rules.password"
                            :help-text="$gettext('Det nuvarande lösenordet måste vara angett under inställningar eller i fältet ovan')"
                            @click:append="form.newPassword = '__generated__'"
                        />
                        <v-alert
                            v-if="endpoint.connection_type === 0"
                            type="info"
                        >
                            <translate>Lösenordet kan endast ändras om det sparade lösenordet är giltigt. Passivt provisionerade system kan inte meddela ev. felstatus.</translate>
                        </v-alert>
                    </v-card-text>
                </v-card>

                <v-checkbox
                    v-if="!form.passiveAnalytics && isCisco"
                    v-model="form.passiveAnalytics"
                    :label="$gettext('Ändra passiv rumsanalys')"
                />
                <v-card
                    v-if="form.passiveAnalytics && isCisco"
                    class="mb-5"
                >
                    <v-card-text>
                        <v-checkbox
                            v-model="form.passiveAnalytics"
                            :label="$gettext('Ändra passiv rumsanalys')"
                            class="mt-0"
                            hide-details
                        />
                    </v-card-text>
                    <v-divider />
                    <v-card-text class="grey lighten-4">
                        <v-checkbox
                            v-model="form.headCount"
                            :label="$gettext('Detektera personantal utanför samtal') + ' (*)'"
                            :disabled="!endpoint.has_head_count && !multiple.length"
                        />
                        <v-checkbox
                            v-model="form.presence"
                            :label="$gettext('Detektera närvaro') + ' (*)'"
                        />
                        <i v-translate>(*) Stöds inte av alla system</i>
                    </v-card-text>
                </v-card>

                <v-checkbox
                    v-model="form.statistics"
                    :label="$gettext('Hämta tidigare statistik')"
                    :disabled="!multiple.length && endpoint.connection_type === 0"
                />

                <v-row v-if="!form.passive">
                    <v-col
                        cols="12"
                        md="6"
                    >
                        <v-checkbox
                            v-model="form.passive"
                            :label="$gettext('Konfigurera passiv provisionering')"
                            persistent-hint
                            :hint="$gettext('Systemet tar kontakt med Rooms med jämna mellanrum för att se om några inställningar ska ändras. Tillåter att styra system som ligger bakom brandvägg eller vid Proxy-fel')"
                        />
                    </v-col>
                    <v-col
                        v-if="!multiple.length"
                        class="pt-md-8 text-md-right"
                    >
                        <v-progress-circular
                            v-if="loading"
                            indeterminate
                            size="24"
                            color="grey lighten-2"
                        />
                        <template v-else-if="provisionStatus">
                            <p>
                                <v-chip
                                    v-if="provisionStatus.passive.this_installation"
                                    small
                                    color="success"
                                >
                                    {{ $gettext('Aktiv') }}
                                </v-chip>
                                <v-chip
                                    v-else
                                    small
                                    :color="provisionStatus.passive.is_set ? 'success' : 'error'"
                                >
                                    {{ provisionStatus.passive.is_set ? $gettext('Annat system') : $gettext('Ej aktiv') }}
                                </v-chip>
                            </p>
                            <p v-if="endpoint.status && endpoint.status.ts_last_provision">
                                <translate>Senast mottagna meddelande</translate>:
                                {{ endpoint.status.ts_last_provision|since }}
                            </p>
                        </template>
                    </v-col>
                </v-row>
                <v-card
                    v-else
                    class="mb-5"
                    :loading="loading"
                >
                    <v-card-text>
                        <v-checkbox
                            v-model="form.passive"
                            :label="$gettext('Konfigurera passiv provisionering')"
                            class="mt-0"
                            persistent-hint
                            :hint="$gettext('Systemet tar kontakt med Rooms med jämna mellanrum för att se om några inställningar ska ändras. Tillåter att styra system som ligger bakom brandvägg eller vid Proxy-fel')"
                        />
                    </v-card-text>
                    <v-divider />
                    <v-card-text class="grey lighten-4">
                        <v-checkbox
                            v-model="form.passiveChain"
                            :label="$gettext('Kedja ihop med extern passiv provisioneringstjänst') + ' (preview)'"
                            class="mt-0"
                            persistent-hint
                            :hint="$gettext('Om systemet idag använder passiv provisionering via en extern tjänst så gör denna inställning så att vissa inställningar och kalenderhändelser fortfarande går att hämta därifrån')"
                        />
                    </v-card-text>
                </v-card>

                <v-row v-if="!form.addressbook">
                    <v-col
                        cols="12"
                        md="6"
                    >
                        <v-checkbox
                            v-model="form.addressbook"
                            :disabled="addressBooks.length === 0"
                            :label="$gettext('Använd adressbok')"
                        />
                    </v-col>
                    <v-col
                        v-if="!multiple.length"
                        class="pt-md-8 text-md-right"
                    >
                        <v-progress-circular
                            v-if="loading"
                            indeterminate
                            size="24"
                            color="grey lighten-2"
                        />
                        <template v-else-if="provisionStatus">
                            <v-chip
                                v-if="provisionStatus.addressbook.id"
                                small
                                color="success"
                            >
                                {{ currentAddressBookTitle || $gettext('Aktiv') }}
                            </v-chip>
                            <v-chip
                                v-else
                                small
                            >
                                {{ provisionStatus.addressbook.is_set ? $gettext('Extern adressbok') : $gettext('Ej aktiv') }}
                            </v-chip>
                        </template>
                    </v-col>
                </v-row>
                <v-card
                    v-if="form.addressbook"
                    class="my-5"
                    :loading="loading"
                >
                    <v-card-text>
                        <v-checkbox
                            v-model="form.addressbook"
                            :label="$gettext('Använd adressbok')"
                            hide-details
                            class="mt-0"
                        />
                    </v-card-text>
                    <v-divider />
                    <v-card-text class="grey lighten-4">
                        <v-select
                            v-model="form.addressBookId"
                            :items="addressBooks"
                            item-text="title"
                            item-value="id"
                        />
                    </v-card-text>
                </v-card>

                <v-checkbox
                    v-if="!form.branding && isCisco"
                    v-model="form.branding"
                    :disabled="brandingProfiles.length === 0"
                    :label="$gettext('Använd branding')"
                />
                <v-card
                    v-if="form.branding && isCisco"
                    class="mb-5"
                    :loading="loading"
                >
                    <v-card-text>
                        <v-checkbox
                            v-model="form.branding"
                            :label="$gettext('Använd branding')"
                            class="mt-0"
                            hide-details
                        />
                    </v-card-text>
                    <v-divider />
                    <v-card-text class="grey lighten-4">
                        <v-select
                            v-model="form.brandingProfileId"
                            :items="brandingProfiles"
                            item-text="name"
                            item-value="id"
                        />
                    </v-card-text>
                </v-card>

                <v-row v-if="!form.firmware && isCisco">
                    <v-col
                        cols="12"
                        md="6"
                    >
                        <v-checkbox
                            v-model="form.firmware"
                            :disabled="firmwares.length === 0"
                            :label="$gettext('Uppgradera firmware')"
                        />
                    </v-col>
                    <v-col
                        v-if="!multiple.length"
                        class="pt-md-8 text-md-right"
                    >
                        <v-chip
                            v-if="endpoint.status && endpoint.status.software_version"
                            small
                        >
                            {{ endpoint.status.software_version }}
                        </v-chip>
                    </v-col>
                </v-row>
                <v-card
                    v-if="form.firmware && isCisco"
                    class="mb-5"
                    :loading="loading"
                >
                    <v-card-text>
                        <v-checkbox
                            v-model="form.firmware"
                            :label="$gettext('Uppgradera firmware')"
                            class="mt-0"
                            hide-details
                        />
                    </v-card-text>
                    <v-divider />
                    <v-card-text class="grey lighten-4">
                        <v-select
                            v-model="form.firmwareId"
                            :items="firmwares"
                            item-text="pretty"
                            item-value="id"
                        />
                        <v-checkbox
                            v-model="form.forceFirmware"
                            :label="$gettext('Forcera installation')"
                        />
                    </v-card-text>
                </v-card>

                <v-checkbox
                    v-model="form.ca_certificates"
                    :disabled="!customerSettings.ca_certificates"
                    :label="$gettext('Installera CA-certifikat')"
                />

                <v-checkbox
                    v-if="!form.controls && isCisco"
                    v-model="form.controls"
                    :disabled="roomControls.length === 0"
                    :label="$gettext('Applicera makron/paneler')"
                />
                <v-card
                    v-if="form.controls && isCisco"
                    class="mb-5"
                    :loading="loading"
                >
                    <v-card-text>
                        <v-checkbox
                            v-model="form.controls"
                            :label="$gettext('Applicera makron/paneler')"
                            class="mt-0"
                            hide-details
                        />
                    </v-card-text>
                    <v-divider />
                    <v-card-text class="grey lighten-4">
                        <v-checkbox
                            v-model="form.clearRoomControls"
                            :label="$gettext('Radera alla befintliga makron/paneler')"
                        />
                        <v-select
                            v-model="form.roomControlIds"
                            :items="roomControls"
                            :label="$gettext('Kontroller')"
                            item-text="title"
                            item-value="id"
                            multiple
                        />
                        <v-select
                            v-model="form.roomControlTemplateIds"
                            :items="roomControlTemplates"
                            :label="$gettext('Samlingar')"
                            item-text="title"
                            item-value="id"
                            multiple
                        />
                    </v-card-text>
                </v-card>

                <v-checkbox
                    v-if="!form.dial"
                    v-model="form.dial"
                    :label="$gettext('Uppringningsegenskaper')"
                />
                <v-card
                    v-if="form.dial"
                    :loading="loading"
                    class="mb-4"
                >
                    <v-card-text>
                        <v-checkbox
                            v-model="form.dial"
                            :label="$gettext('Uppringningsegenskaper')"
                            class="mt-0"
                            hide-details
                        />
                    </v-card-text>
                    <v-divider />
                    <v-card-text class="grey lighten-4">
                        <template v-if="!multiple.length">
                            <v-text-field
                                v-model="form.dialSettings.name "
                                :label="$gettext('System Name')"
                                :disabled="cloudRegistered || form.dialSettings.current"
                            />
                            <p v-if="differencingDialSettings.name">
                                <translate>Nuvarande värde</translate>: <a
                                    href="#"
                                    @click.prevent="form.dialSettings.name = differencingDialSettings.name"
                                >{{ differencingDialSettings.name || $gettext('-- tomt --') }}</a>
                            </p>
                        </template>

                        <template v-if="!cloudRegistered && !multiple.length">
                            <v-text-field
                                v-model="form.dialSettings.sip"
                                :label="$gettext('SIP URI')"
                                :disabled="!!multiple.length || cloudRegistered || form.dialSettings.current"
                            />
                            <p v-if="differencingDialSettings.sip">
                                <translate>Nuvarande värde</translate>: <a
                                    href="#"
                                    @click.prevent="form.dialSettings.sip = differencingDialSettings.sip"
                                >{{ differencingDialSettings.sip || $gettext('-- tomt --') }}</a>
                            </p>


                            <v-text-field
                                v-model="form.dialSettings.sip_display_name"
                                :label="$gettext('SIP Display name')"
                                :disabled="!!multiple.length || cloudRegistered || form.dialSettings.current"
                            />

                            <p v-if="differencingDialSettings.sip_display_name">
                                <translate>Nuvarande värde</translate>: <a
                                    href="#"
                                    @click.prevent="form.dialSettings.sip_display_name = differencingDialSettings.sip_display_name"
                                >{{ differencingDialSettings.sip_display_name || $gettext('-- tomt --') }}</a>
                            </p>

                            <v-text-field
                                v-model="form.dialSettings.h323"
                                :label="$gettext('H323 ID')"
                                :counter="49"
                                :disabled="!!multiple.length || cloudRegistered || form.dialSettings.current"
                            />

                            <p v-if="differencingDialSettings.h323">
                                <translate>Nuvarande värde</translate>: <a
                                    href="#"
                                    @click.prevent="form.dialSettings.h323 = differencingDialSettings.h323"
                                >{{ differencingDialSettings.h323 || $gettext('-- tomt --') }}</a>
                            </p>

                            <v-text-field
                                v-model="form.dialSettings.h323_e164"
                                :label="$gettext('E.164')"
                                :counter="30"
                                :disabled="!!multiple.length || cloudRegistered || form.dialSettings.current"
                            />

                            <p v-if="differencingDialSettings.h323_e164">
                                <translate>Nuvarande värde</translate>: <a
                                    href="#"
                                    @click.prevent="form.dialSettings.h323_e164 = differencingDialSettings.h323_e164"
                                >{{ differencingDialSettings.h323_e164 || $gettext('-- tomt --') }}</a>
                            </p>
                        </template>

                        <div v-if="endpoint.webex_registration && !multiple.length">
                            <translate>Systemet är Webex-registrerat</translate>
                        </div>
                        <div v-if="endpoint.pexip_registration && !multiple.length">
                            <translate>Systemet är Pexip.me-registrerat</translate>
                        </div>
                        <template v-else>
                            <v-text-field
                                v-model="form.dialSettings.sip_proxy"
                                :label="$gettext('SIP Proxy')"
                                :disabled="cloudRegistered && !multiple.length"
                            />

                            <p v-if="differencingDialSettings.sip_proxy">
                                <translate>Nuvarande värde</translate>: <a
                                    href="#"
                                    @click.prevent="form.dialSettings.sip_proxy = differencingDialSettings.sip_proxy"
                                >{{ differencingDialSettings.sip_proxy || $gettext('-- tomt --') }}</a>
                            </p>

                            <v-text-field
                                v-model="form.dialSettings.sip_proxy_username"
                                :label="$gettext('SIP Proxy username')"
                                :disabled="cloudRegistered && !multiple.length"
                            />

                            <p v-if="differencingDialSettings.sip_proxy_username">
                                <translate>Nuvarande värde</translate>: <a
                                    href="#"
                                    @click.prevent="form.dialSettings.sip_proxy_username = differencingDialSettings.sip_proxy_username"
                                >{{ differencingDialSettings.sip_proxy_username || $gettext('-- tomt --') }}</a>
                            </p>

                            <v-text-field
                                v-model="form.dialSettings.sip_proxy_password"
                                :label="$gettext('SIP Proxy password')"
                                :disabled="cloudRegistered && !multiple.length"
                                type="password"
                            />
                            <v-text-field
                                v-model="form.dialSettings.h323_gatekeeper"
                                :label="$gettext('H323 gatekeeper')"
                                :disabled="cloudRegistered && !multiple.length"
                            />

                            <p v-if="differencingDialSettings.h323_gatekeeper">
                                <translate>Nuvarande värde</translate>: <a
                                    href="#"
                                    @click.prevent="form.dialSettings.h323_gatekeeper = differencingDialSettings.h323_gatekeeper"
                                >{{ differencingDialSettings.h323_gatekeeper || $gettext('-- tomt --') }}</a>
                            </p>

                            <v-checkbox
                                v-if="form.dialSettings.current || multiple.length"
                                v-model="form.dialSettings.current"
                                :label="$gettext('Provisionera sparade uppgifter')"
                            />

                            <v-checkbox
                                v-if="isPexip"
                                v-model="form.dialSettings.register"
                                :label="$gettext('Registrera nya alias i Pexip')"
                                :disabled="cloudRegistered && !multiple.length"
                            />
                        </template>
                    </v-card-text>
                </v-card>
            </v-card-text>

            <ErrorMessage :error="error" />
            <v-divider />
            <v-card-actions :class="{ 'px-0': !dialog }">
                <v-btn
                    color="primary"
                    :loading="resultLoading"
                    @click="apply()"
                >
                    <translate>Tillämpa</translate>
                </v-btn>
                <v-menu offset-y>
                    <v-list>
                        <v-list-item
                            @click="apply('night')"
                        >
                            <v-list-item-title>
                                <translate>Till natten</translate>
                            </v-list-item-title>
                        </v-list-item>
                        <v-list-item
                            @click="apply('night', { repeat: true })"
                        >
                            <v-list-item-title>
                                <translate>Varje natt</translate>
                            </v-list-item-title>
                        </v-list-item>
                    </v-list>

                    <template v-slot:activator="{ on, attrs }">
                        <v-btn
                            class="ml-2"
                            color="primary"
                            outlined
                            :loading="resultLoading"
                            v-bind="attrs"
                            v-on="on"
                        >
                            <translate>Schemalägg</translate>
                        </v-btn>
                    </template>
                </v-menu>

                <v-spacer />
                <v-btn
                    v-if="dialog"
                    v-close-dialog
                    text
                    color="red"
                >
                    <translate>Avbryt</translate>
                    <v-icon
                        right
                        dark
                    >
                        mdi-close
                    </v-icon>
                </v-btn>
            </v-card-actions>
        </v-card>

        <EndpointProvisionResult
            ref="provisionDialog"
            v-model="resultDialog"
            :endpoints="endpointIds"
            @update:loading="resultLoading = $event"
            @update:error="error = $event"
        />

        <v-snackbar v-model="form.createdSnackbar">
            <translate>Sparat</translate>
        </v-snackbar>
    </v-form>
</template>

<script>
import SingleEndpointMixin from '@/vue/views/epm/mixins/SingleEndpointMixin'
import EndpointGrid from '@/vue/components/epm/endpoint/EndpointGrid'
import EndpointConfigurationForm from '@/vue/components/epm/endpoint/EndpointConfigurationForm'
import EndpointTemplateGrid from '@/vue/components/epm/EndpointTemplateGrid'
import {
    filterInternalSettings,
    flattenConfigurationTree,
    populateSettingsData,
} from '@/vue/store/modules/endpoint/helpers'
import ConfigurationWrapper from '@/vue/components/epm/endpoint/ConfigurationWrapper'
import EndpointStatus from '@/vue/components/epm/EndpointStatus'
import ErrorMessage from '@/vue/components/base/ErrorMessage'
import { timestamp } from '@/vue/helpers/datetime'
import SaveTemplateDialog from '@/vue/components/epm/endpoint/SaveTemplateDialog'
import { EndpointManufacturer, PLACEHOLDER_PASSWORD } from '@/vue/store/modules/endpoint/consts'
import EndpointProvisionResult from '@/vue/views/epm/endpoint/single/EndpointProvisionResult'
import { GlobalEventBus } from '@/vue/helpers/events'

export default {
    components: {
        EndpointProvisionResult,
        SaveTemplateDialog,
        ErrorMessage,
        EndpointStatus,
        EndpointTemplateGrid,
        ConfigurationWrapper,
        EndpointGrid,
        EndpointConfigurationForm,
    },
    mixins: [SingleEndpointMixin],
    props: {
        multiple: {
            type: Array,
            default() {
                return []
            },
        },
        dialog: Boolean,
    },
    // eslint-disable-next-line max-lines-per-function
    data() {
        return {
            loading: true,
            loadingCommands: false,
            loadingConfigurations: false,

            resultDialog: false,
            resultLoading: false,

            editSetting: null,
            editCommand: null,
            provisionId: null,

            form: {
                configuration: false,
                commands: false,
                events: true,
                password: false,
                addressbook: false,
                firmware: false,
                branding: false,
                dial: false,
                controls: false,

                statistics: false, // very slow
                passive: false, // TODO true if proxy and no other provisioning
                passiveChain: false,

                selectedConfigurationTemplates: [],
                selectedCommandTemplates: [],

                configurationEndpoint: [],
                commandsEndpoint: [],

                useStandardPassword: true,
                newPassword: '',
                currentPassword: '',
                ca_certificates: false,
                dialSettings: {
                    current: false,
                    name: '',
                    sip: '',
                    sip_display_name: '',
                    h323: '',
                    h323_e164: '',
                    sip_proxy: '',
                    sip_proxy_username: '',
                    sip_proxy_password: '',
                    h323_gatekeeper: '',
                    register: false,
                },
                passiveAnalytics: true,
                headCount: true,
                presence: true,
                configurationTab: false,
                commandsTab: 0,
                addressBookId: null,
                brandingProfileId: null,
                firmwareId: null,
                forceFirmware: null,
                clearRoomControls: false,
                roomControlIds: [],
                roomControlTemplateIds: [],
            },
            templateForm: {
                templateDialog: false,
                activeEndpoint: null,
            },
            informationTemplate: null,
            provisionStatus: null,

            endpointConfigurationLoading: false,
            endpointCommandsLoading: false,
            createdSnackbar: null,
            error: null,
            firstLoad: true,

            emitter: new GlobalEventBus(this),
        }
    },
    computed: {
        addressBooks() {
            return this.$store.getters['addressbook/addressBooks']
        },
        currentAddressBookTitle() {
            if (!this.provisionStatus?.addressbook?.id) return
            return this.$store.state.addressbook.books[this.provisionStatus.addressbook.id]?.title
        },
        brandingProfiles() {
            return Object.values(this.$store.state.endpoint_branding.profiles)
        },
        endpoints() {
            const endpoints = this.$store.state.endpoint.endpoints
            return this.multiple.map(id => endpoints[id])
        },
        endpointIds() {
            return this.multiple.length ? this.multiple : [this.id]
        },
        customerSettings() {
            return this.$store.state.endpoint.settings || {}
        },
        configurationTemplates() {
            return Object.values(this.$store.state.endpoint.templates).filter(t => t.settings && !!t.settings.length)
        },
        commandTemplates() {
            return Object.values(this.$store.state.endpoint.templates).filter(t => t.commands && !!t.commands.length)
        },
        cloudRegistered() {
            return this.endpoint.webex_registration || this.endpoint.pexip_registration
        },
        firmwares() {
            return Object.values(
                this.$store.state.endpoint.firmwares || {}
            ).filter(f => f.model == this.endpoint.product_name)
                .map(f => ({
                    ...f,
                    pretty: `${f.version} (${timestamp(f.ts_created)})`
                }))
        },
        activeConfiguration() {
            return Object.values(this.$store.state.endpoint.activeConfiguration)
        },
        commandQueue() {
            return Object.values(this.$store.state.endpoint.commandQueue)
        },
        roomControls() {
            return Object.values(this.$store.state.roomcontrol.controls || {})
        },
        roomControlTemplates() {
            return Object.values(this.$store.state.roomcontrol.templates || {})
        },
        isPexip() {
            return this.$store.state.site.isPexip
        },
        differencingDialSettings() {
            if (!this.provisionStatus || this.multiple.length || !this.form.dialSettings) return {}

            const result = {}

            const dial = this.provisionStatus.dial_settings
            Object.keys(this.provisionStatus.dial_settings).forEach(key => {
                if (key in dial && key in this.form.dialSettings) {
                    if (dial[key] !== this.form.dialSettings[key]) result[key] = dial[key]
                }
            })

            return result
        },
        rules() {
            return {
                password: [v => !v || v.length <= 6 ? this.$gettext('Lösenordet måste innehålla minst 6 tecken') : true]
            }
        },
        isCisco() {
            return this.endpoint.manufacturer == EndpointManufacturer.cisco
        }
    },
    watch: {
        id() {
            this.loadData()
        },
        'multiple.length'() {
            this.loadData()
        }
    },
    mounted() {
        this.emitter.on('refresh', () => this.loadData())
        return this.loadData()
    },
    methods: {
        loadData() {
            this.loading = true
            return Promise.all([
                this.loadRelatedItems(),
            ]).catch(e => {
                this.error = e
            }).then(() => {
                this.loading = false
                this.emitter.emit('loading', false)
            })
        },
        getCurrentDialInfo() {
            const settings = this.customerSettings
            const hasPassword = settings.sip_proxy_password || settings.has_sip_proxy_password

            return {
                ...this.form.dialSettings,
                name: this.endpoint.title,
                sip: this.endpoint.sip,
                h323: this.endpoint.h323,
                h323_e164: this.endpoint.h323_e164,
                sip_proxy: settings.sip_proxy || '',
                sip_proxy_username: settings.sip_proxy_username || '',
                sip_proxy_password: hasPassword ? PLACEHOLDER_PASSWORD : '',
                h323_gatekeeper: settings.h323_gatekeeper || '',
            }
        },
        populateDialInfo(dialInfo) {

            let changeDial = false

            const result = this.getCurrentDialInfo()
            if (dialInfo) {
                ['name', 'sip_display_name', 'sip', 'h323', 'h323_e164'].forEach(k => {
                    if (result[k] && result[k] != dialInfo[k]) changeDial = true

                    result[k] = result[k] || dialInfo[k] || ''
                });

                ['sip_proxy', 'sip_proxy_username', 'sip_proxy_password', 'h323_gatekeeper'].forEach(k => {
                    result[k] = dialInfo[k] || result[k] || ''
                })

            }
            this.form.dialSettings = result
            if (this.endpoint.title !== result.name) this.form.dial = true
            if (!this.cloudRegistered && changeDial) {
                this.form.dial = true
            }
        },
        loadProvisionStatus() {
            return this.$store
                .dispatch('endpoint/getProvisionStatus', this.id)
                .then(status => {
                    this.provisionStatus = status
                    this.populateDialInfo(status.dial_settings)
                    return status
                })
                .catch(e => {
                    this.populateDialInfo()
                    throw e
                })
        },
        loadRelatedItems() {
            return Promise.all([
                this.$store.dispatch('endpoint/getTemplates'),
                this.$store.dispatch('endpoint/getSettings'),
                this.$store.dispatch('addressbook/getAddressBooks'),
                this.$store.dispatch('endpoint/getFirmwares', this.endpoint.manufacturer),
                this.$store.dispatch('endpoint_branding/loadProfiles'),
                this.$store.dispatch('roomcontrol/getControls'),
                this.$store.dispatch('roomcontrol/getTemplates'),
                ...(
                    this.multiple.length ? [] :
                        [this.loadProvisionStatus().catch(void {})]
                ),
            ]).then(values => {
                this.loading = false
                this.populateRelatedItems(values[1])
                this.firstLoad = false
                if (this.multiple.length) {
                    this.populateDialInfo()
                }
            })
        },
        // eslint-disable-next-line sonarjs/cognitive-complexity
        populateRelatedItems(settings) {
            if (settings.default_address_book) {
                this.form.addressBookId = settings.default_address_book
            }
            if (settings.default_branding_profile) {
                this.form.brandingProfileId = settings.default_branding_profile
                // if (this.firstLoad) this.form.branding = true // TODO save provisioned id
            }

            if (this.firstLoad && !this.multiple.length && this.provisionStatus) {
                if (!this.provisionStatus?.addressbook?.is_set && this.addressBooks.length) this.form.addressbook = true
                if (this.provisionStatus?.addressbook?.id) this.form.addressBookId = this.provisionStatus.addressbook.id
                this.form.events = !this.provisionStatus.event

                if (this.provisionStatus.analytics.head_count === null && this.provisionStatus.analytics.presence === null) {
                    this.form.passiveAnalytics = false
                }
            }

            if (settings.ca_certificates) {
                this.form.ca_certificates = true
            }

            if (this.addressBooks.length === 1) this.form.addressBookId = this.addressBooks[0].id
            if (this.firmwares.length === 1) this.form.firmwareId = this.firmwares[0].id
            if (this.brandingProfiles.length === 1) this.form.brandingProfileId = this.brandingProfiles[0].id

            if (this.addressBooks.length === 0) this.form.addressbook = false
            if (this.firmwares.length === 0) this.form.firmware = false
            if (this.brandingProfiles.length === 0) this.form.branding = false

            if (this.endpoint.personal_system && this.firstLoad) {
                this.form.passiveAnalytics = false
                this.form.headCount = false
                this.form.presence = false
            }
        },
        loadConfigurationTemplate(template) {
            this.loadingConfigurations = true

            return this.getConfiguration()
                .catch(() => {
                    this.loadingConfigurations = false
                })
                .then(configuration => {
                    this.$store.commit(
                        'endpoint/setActiveConfiguration',
                        populateSettingsData(template.settings, configuration)
                    )
                    this.form.configurationTab = 3
                    this.loadingConfigurations = false
                })
        },
        async loadCommandTemplate(template) {
            this.loadingCommands = true

            try {
                await this.$store.dispatch('endpoint/getCommands', this.id)
            } catch (e) {
                //
            }

            const allCommands = this.$store.state.endpoint.commands[this.id]?.data || []

            const commands = template.commands.map(command => {
                let commandMeta = null
                allCommands.map(c => {
                    if (c[3] && c[3].path.join('/') === command.command.join('/')) commandMeta = c
                })
                return {...command, command: { path: command.command }, ...commandMeta}
            })
            this.$store.commit('endpoint/setCommandQueue', commands)
            this.form.commandsTab = 1
            this.loadingCommands = false
            return commands
        },
        loadEndpoint(endpoint) {
            this.endpointConfigurationLoading = true

            return this.$store.dispatch('endpoint/getConfiguration', endpoint.id).then(configuration => {
                this.endpointConfigurationLoading = false

                const settings = filterInternalSettings(flattenConfigurationTree(configuration)).map(s => ({
                    ...s,
                    setting: s,
                }))
                this.$store.commit('endpoint/setActiveConfiguration', settings)

                this.templateForm.activeEndpoint = endpoint
                this.form.configurationTab = 3
            })
        },
        getConfiguration() {
            const existing = this.$store.state.endpoint.configuration[this.id]?.data
            return existing
                ? Promise.resolve(existing)
                : this.$store
                    .dispatch('endpoint/getConfiguration', this.id)
                    .then(() => this.$store.state.endpoint.configuration[this.id]?.data)
        },
        // eslint-disable-next-line max-lines-per-function,sonarjs/cognitive-complexity
        serializedData() {
            const result = {}

            const form = this.form

            if (form.addressbook && form.addressBookId) {
                result.addressbook = form.addressBookId
            }

            if (form.firmware && form.firmwareId) {
                result.firmware = form.firmwareId
                result.force_firmware = form.forceFirmware
            }

            if (form.events) {
                result.events = true
            }

            if (form.configuration) {
                result.configuration = this.activeConfiguration.map(c => ({ key: c.path, value: c.value }))
            }

            if (form.commands) {
                result.commands = this.commandQueue.map(c => ({command: c.command.path, body: c.body, arguments: c.arguments }))
            }

            if (form.passiveAnalytics) {
                if (this.endpoint.has_head_count || this.multiple.length) {
                    result.head_count = !!form.headCount
                }
                result.presence = !!form.presence
            }

            if (form.branding) {
                result.branding_profile = form.brandingProfileId
            }

            if (form.ca_certificates) {
                result.ca_certificates = !!form.ca_certificates
            }

            if (form.controls) {
                result.clear_room_controls = form.clearRoomControls
                result.room_controls = form.roomControlIds
                result.room_control_templates = form.roomControlTemplateIds
            }

            result.statistics = form.statistics
            result.passive = form.passive
            result.passive_chain = form.passiveChain

            if (form.password) {
                result.set_password = true
                if (form.useStandardPassword) {
                    result.standard_password = true
                } else {
                    result.password = form.newPassword
                    result.current_password = form.currentPassword || undefined
                }
            }

            if (form.dial) {
                if (!this.multiple.length || (this.multiple.length == 1 && this.id == this.multiple[0])) {
                    if (this.endpoint.webex_registration) {
                        result.dial_info = { name: this.form.dialSettings.name }
                    } else {
                        result.dial_info = form.dialSettings
                    }
                } else {
                    const d = form.dialSettings
                    result.dial_info = {
                        sip_proxy: d.sip_proxy,
                        sip_proxy_username: d.sip_proxy_username || undefined,
                        sip_proxy_password: d.sip_proxy_password || undefined,
                        h323_gatekeeper: d.h323_gatekeeper || undefined,
                        register: d.register,
                        current: d.current || undefined,
                    }
                }
            }

            return result
        },
        apply(constraint=undefined, extra=undefined) {
            const data = this.serializedData()
            if (extra) Object.assign(data, extra)

            return this.$refs.provisionDialog.apply({constraint, ...data}).catch(() => null)
        },
    },
}
</script>
