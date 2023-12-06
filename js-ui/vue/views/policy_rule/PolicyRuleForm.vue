<template>
    <v-form
        v-if="!loading"
        ref="form"
        v-model="formValid"
        @submit.prevent="submit"
    >
        <v-card>
            <div v-if="loading">
                <v-progress-circular indeterminate />
            </div>
            <v-card-title>
                <span v-if="id"><translate>Redigera regel</translate></span>
                <span v-else><translate>Lägg till regel</translate></span>
            </v-card-title>
            <v-divider />
            <v-tabs v-model="tab">
                <v-tab><translate>General</translate></v-tab>
                <v-tab><translate>Match</translate></v-tab>
                <v-tab><translate>Media settings</translate></v-tab>
                <v-tab><translate>Outgoing</translate></v-tab>
            </v-tabs>
            <v-divider />
            <v-card-text class="pa-0">
                <v-tabs-items v-model="tab">
                    <v-tab-item eager>
                        <v-card flat>
                            <v-card-text>
                                <v-checkbox
                                    v-model="form.enable"
                                    :error-messages="errors.enable ? errors.enable : []"
                                    :rules="rules.enable"
                                    :label="$gettext('Enable this rule')"
                                    class="mt-2"
                                >
                                    <template v-slot:append>
                                        <v-tooltip
                                            left
                                            :max-width="420"
                                        >
                                            <template v-slot:activator="{ on, attrs }">
                                                <v-icon
                                                    v-bind="attrs"
                                                    v-on="on"
                                                >
                                                    mdi-information
                                                </v-icon>
                                            </template>
                                            <translate>
                                                Determines whether or not the rule is enabled. Any disabled rules still
                                                appear in the rules list but are ignored. Use this setting to test
                                                configuration changes, or to temporarily disable specific
                                                rules.
                                            </translate>
                                        </v-tooltip>
                                    </template>
                                </v-checkbox>
                                <v-checkbox
                                    v-model="form.is_fallback"
                                    :error-messages="errors.is_fallback ? errors.is_fallback : []"
                                    :rules="rules.is_fallback"
                                    :label="$gettext('Is fallback')"
                                    class="mt-2"
                                >
                                    <template v-slot:append>
                                        <v-tooltip
                                            left
                                            :max-width="420"
                                        >
                                            <template v-slot:activator="{ on, attrs }">
                                                <v-icon
                                                    v-bind="attrs"
                                                    v-on="on"
                                                >
                                                    mdi-information
                                                </v-icon>
                                            </template>
                                            <translate>This is a fallback rule. These will always be placed last</translate>
                                        </v-tooltip>
                                    </template>
                                </v-checkbox>
                                <v-checkbox
                                    v-model="form.sync_back"
                                    :error-messages="errors.sync_back ? errors.sync_back : []"
                                    :rules="rules.sync_back"
                                    :label="$gettext('Sync back to Pexip')"
                                    class="mt-2"
                                >
                                    <template v-slot:append>
                                        <v-tooltip
                                            left
                                            :max-width="420"
                                        >
                                            <template v-slot:activator="{ on, attrs }">
                                                <v-icon
                                                    v-bind="attrs"
                                                    v-on="on"
                                                >
                                                    mdi-information
                                                </v-icon>
                                            </template>
                                            <translate>This rule will be synced back to pexip.</translate>
                                        </v-tooltip>
                                    </template>
                                </v-checkbox>

                                <v-card class="mt-4">
                                    <v-card-text>
                                        <v-text-field
                                            v-model="form.name"
                                            :error-messages="errors.name ? errors.name : []"
                                            :rules="rules.name"
                                            clearable
                                            label="Name (*)"
                                            :counter="250"
                                        >
                                            <template v-slot:append-outer>
                                                <v-tooltip
                                                    left
                                                    :max-width="420"
                                                >
                                                    <template v-slot:activator="{ on, attrs }">
                                                        <v-icon
                                                            v-bind="attrs"
                                                            v-on="on"
                                                        >
                                                            mdi-information
                                                        </v-icon>
                                                    </template>
                                                    <translate>The name used to refer to this Call Routing Rule.</translate>
                                                </v-tooltip>
                                            </template>
                                        </v-text-field>
                                        <v-text-field
                                            v-model="form.tag"
                                            :error-messages="errors.tag ? errors.tag : []"
                                            :rules="rules.tag"
                                            clearable
                                            :label="$gettext('Service tag')"
                                            :counter="250"
                                        >
                                            <template
                                                v-slot:append-outer
                                            >
                                                <v-tooltip
                                                    left
                                                    :max-width="420"
                                                >
                                                    <template
                                                        v-slot:activator="{ on, attrs }"
                                                    >
                                                        <v-icon
                                                            v-bind="attrs"
                                                            v-on="on"
                                                        >
                                                            mdi-information
                                                        </v-icon>
                                                    </template><translate>
                                                        A unique identifier used to track usage of this Call Routing
                                                        Rule.
                                                    </translate>
                                                </v-tooltip>
                                            </template>
                                        </v-text-field>
                                        <v-text-field
                                            v-model="form.description"
                                            :error-messages="errors.description ? errors.description : []"
                                            :rules="rules.description"
                                            clearable
                                            :label="$gettext('Description')"
                                            :counter="250"
                                        >
                                            <template
                                                v-slot:append-outer
                                            >
                                                <v-tooltip
                                                    left
                                                    :max-width="420"
                                                >
                                                    <template
                                                        v-slot:activator="{ on, attrs }"
                                                    >
                                                        <v-icon
                                                            v-bind="attrs"
                                                            v-on="on"
                                                        >
                                                            mdi-information
                                                        </v-icon>
                                                    </template><translate>A description of the Call Routing Rule.</translate>
                                                </v-tooltip>
                                            </template>
                                        </v-text-field>
                                        <v-text-field
                                            v-model.number="form.priority"
                                            type="number"
                                            :error-messages="errors.priority ? errors.priority : []"
                                            :rules="rules.priority"
                                            :label="$gettext('Priority')"
                                        >
                                            <template
                                                v-slot:append-outer
                                            >
                                                <v-tooltip
                                                    left
                                                    :max-width="420"
                                                >
                                                    <template
                                                        v-slot:activator="{ on, attrs }"
                                                    >
                                                        <v-icon
                                                            v-bind="attrs"
                                                            v-on="on"
                                                        >
                                                            mdi-information
                                                        </v-icon>
                                                    </template><translate>
                                                        The priority of this rule. Rules are checked in ascending priority
                                                        order until the first matching rule is found, and it is then applied.
                                                        Range: 1 to 200.
                                                    </translate>
                                                </v-tooltip>
                                            </template>
                                        </v-text-field>
                                    </v-card-text>
                                </v-card>
                            </v-card-text>
                        </v-card>
                    </v-tab-item>
                    <v-tab-item eager>
                        <v-card flat>
                            <v-card-text>
                                <v-card :flat="!form.match_incoming_calls">
                                    <v-card-text :class="{ 'pa-0': !form.match_incoming_calls, 'mb-4': form.match_incoming_calls }">
                                        <v-checkbox
                                            v-model="form.match_incoming_calls"
                                            :error-messages="
                                                errors.match_incoming_calls ? errors.match_incoming_calls : []
                                            "
                                            :rules="rules.match_incoming_calls"
                                            :label="$gettext('Match incoming gateway calls')"
                                            class="mt-2"
                                        >
                                            <template v-slot:append>
                                                <v-tooltip
                                                    left
                                                    :max-width="420"
                                                >
                                                    <template v-slot:activator="{ on, attrs }">
                                                        <v-icon
                                                            v-bind="attrs"
                                                            v-on="on"
                                                        >
                                                            mdi-information
                                                        </v-icon>
                                                    </template>
                                                    <translate>
                                                        Applies this rule to incoming calls that have not been routed to a
                                                        Virtual Meeting Room or Virtual Reception, and should be routed via
                                                        the Pexip Distributed Gateway service.
                                                    </translate>
                                                </v-tooltip>
                                            </template>
                                        </v-checkbox>
                                        <div v-if="form.match_incoming_calls">
                                            <v-text-field
                                                v-model="form.match_source_alias"
                                                :error-messages="
                                                    errors.match_source_alias ? errors.match_source_alias : []
                                                "
                                                :rules="rules.match_source_alias"
                                                clearable
                                                :label="$gettext('Match source alias address')"
                                                :counter="250"
                                            />
                                            <v-select
                                                v-model="form.match_source_location"
                                                :error-messages="
                                                    errors.match_source_location ? errors.match_source_location : []
                                                "
                                                :rules="rules.match_source_location"
                                                :label="$gettext('Calls being handled in location')"
                                                clearable
                                                :items="match_source_locations"
                                                item-text="name"
                                                item-value="id"
                                            >
                                                <template
                                                    v-slot:append-outer
                                                >
                                                    <v-tooltip
                                                        left
                                                        :max-width="420"
                                                    >
                                                        <template
                                                            v-slot:activator="{ on, attrs }"
                                                        >
                                                            <v-icon
                                                                v-bind="attrs"
                                                                v-on="on"
                                                            >
                                                                mdi-information
                                                            </v-icon>
                                                        </template><translate>
                                                            Applies the rule only if the incoming call is being handled by a
                                                            Conferencing Node in the selected location or the outgoing call is
                                                            being initiated from the selected location. To apply the rule
                                                            regardless of the location, select Any Location.
                                                        </translate>
                                                    </v-tooltip>
                                                </template>
                                            </v-select>
                                            <v-select
                                                v-if="form.match_source_alias && form.match_source_location"
                                                v-model="form.match_source_mode"
                                                :items="choices.match_source_mode"
                                                :label="$gettext('Match mode')"
                                                item-text="text"
                                                item-value="key"
                                            />
                                            <v-checkbox
                                                v-model="form.match_incoming_only_if_registered"
                                                :error-messages="
                                                    errors.match_incoming_only_if_registered
                                                        ? errors.match_incoming_only_if_registered
                                                        : []
                                                "
                                                :rules="rules.match_incoming_only_if_registered"
                                                :label="$gettext('Match incoming calls from registered devices only')"
                                                class="mt-2"
                                            >
                                                <template v-slot:append>
                                                    <v-tooltip
                                                        left
                                                        :max-width="420"
                                                    >
                                                        <template v-slot:activator="{ on, attrs }">
                                                            <v-icon
                                                                v-bind="attrs"
                                                                v-on="on"
                                                            >
                                                                mdi-information
                                                            </v-icon>
                                                        </template>
                                                        <translate>
                                                            Only apply this rule to incoming calls from devices,
                                                            videoconferencing endpoints, soft clients or Infinity Connect clients
                                                            that are registered to Pexip Infinity. Note that the call must also
                                                            match one of the selected protocols below. Calls placed from
                                                            non-registered clients or devices, or from the Infinity Connect Web
                                                            App will not be routed by this rule if it is enabled.
                                                        </translate>
                                                    </v-tooltip>
                                                </template>
                                            </v-checkbox>
                                            <v-checkbox
                                                v-model="form.match_incoming_webrtc"
                                                :error-messages="
                                                    errors.match_incoming_webrtc
                                                        ? errors.match_incoming_webrtc
                                                        : []
                                                "
                                                :rules="rules.match_incoming_webrtc"
                                                label="Match Infinity Connect (WebRTC / RTMP)"
                                                class="mt-2"
                                            >
                                                <template v-slot:append>
                                                    <v-tooltip
                                                        left
                                                        :max-width="420"
                                                    >
                                                        <template v-slot:activator="{ on, attrs }">
                                                            <v-icon
                                                                v-bind="attrs"
                                                                v-on="on"
                                                            >
                                                                mdi-information
                                                            </v-icon>
                                                        </template>
                                                        <translate>
                                                            Select whether this rule should apply to incoming calls from Infinity
                                                            Connect clients
                                                        </translate> (WebRTC / RTMP).
                                                    </v-tooltip>
                                                </template>
                                            </v-checkbox>
                                            <v-checkbox
                                                v-model="form.match_incoming_sip"
                                                :error-messages="
                                                    errors.match_incoming_sip ? errors.match_incoming_sip : []
                                                "
                                                :rules="rules.match_incoming_sip"
                                                :label="$gettext('Match SIP')"
                                                class="mt-2"
                                            >
                                                <template v-slot:append>
                                                    <v-tooltip
                                                        left
                                                        :max-width="420"
                                                    >
                                                        <template v-slot:activator="{ on, attrs }">
                                                            <v-icon
                                                                v-bind="attrs"
                                                                v-on="on"
                                                            >
                                                                mdi-information
                                                            </v-icon>
                                                        </template>
                                                        <translate>
                                                            Select whether this rule should apply to incoming SIP
                                                            calls.
                                                        </translate>
                                                    </v-tooltip>
                                                </template>
                                            </v-checkbox>
                                            <v-checkbox
                                                v-model="form.match_incoming_mssip"
                                                :error-messages="
                                                    errors.match_incoming_mssip ? errors.match_incoming_mssip : []
                                                "
                                                :rules="rules.match_incoming_mssip"
                                                label="Match Lync / Skype for Business (MS-SIP)"
                                                class="mt-2"
                                            >
                                                <template v-slot:append>
                                                    <v-tooltip
                                                        left
                                                        :max-width="420"
                                                    >
                                                        <template v-slot:activator="{ on, attrs }">
                                                            <v-icon
                                                                v-bind="attrs"
                                                                v-on="on"
                                                            >
                                                                mdi-information
                                                            </v-icon>
                                                        </template>
                                                        <translate>
                                                            Select whether this rule should apply to incoming Lync / Skype for
                                                            Business
                                                        </translate> (MS-SIP) calls.
                                                    </v-tooltip>
                                                </template>
                                            </v-checkbox>
                                            <v-checkbox
                                                v-model="form.match_incoming_h323"
                                                :error-messages="
                                                    errors.match_incoming_h323 ? errors.match_incoming_h323 : []
                                                "
                                                :rules="rules.match_incoming_h323"
                                                :label="$gettext('Match H.323')"
                                                class="mt-2"
                                            >
                                                <template v-slot:append>
                                                    <v-tooltip
                                                        left
                                                        :max-width="420"
                                                    >
                                                        <template v-slot:activator="{ on, attrs }">
                                                            <v-icon
                                                                v-bind="attrs"
                                                                v-on="on"
                                                            >
                                                                mdi-information
                                                            </v-icon>
                                                        </template>
                                                        <translate>
                                                            Select whether this rule should apply to incoming H.323
                                                            calls.
                                                        </translate>
                                                    </v-tooltip>
                                                </template>
                                            </v-checkbox>
                                        </div>
                                    </v-card-text>
                                </v-card>

                                <v-checkbox
                                    v-model="form.match_outgoing_calls"
                                    solo
                                    :error-messages="
                                        errors.match_outgoing_calls ? errors.match_outgoing_calls : []
                                    "
                                    :rules="rules.match_outgoing_calls"
                                    :label="$gettext('Match outgoing calls from a conference')"
                                    class="mt-2"
                                >
                                    <template v-slot:append>
                                        <v-tooltip
                                            left
                                            :max-width="420"
                                        >
                                            <template v-slot:activator="{ on, attrs }">
                                                <v-icon
                                                    v-bind="attrs"
                                                    v-on="on"
                                                >
                                                    mdi-information
                                                </v-icon>
                                            </template><translate>Applies this rule to outgoing calls placed from a conference service</translate>
                                            (e.g. when adding a participant to a Virtual Meeting Room) where
                                            Automatic routing has been selected.
                                        </v-tooltip>
                                    </template>
                                </v-checkbox>
                                <v-checkbox
                                    v-model="form.match_string_full"
                                    :error-messages="errors.match_string_full ? errors.match_string_full : []"
                                    :rules="rules.match_string_full"
                                    :label="$gettext('Match against full alias URI')"
                                    class="mt-2"
                                >
                                    <template
                                        v-slot:append
                                    >
                                        <v-tooltip
                                            left
                                            :max-width="420"
                                        >
                                            <template
                                                v-slot:activator="{ on, attrs }"
                                            >
                                                <v-icon
                                                    v-bind="attrs"
                                                    v-on="on"
                                                >
                                                    mdi-information
                                                </v-icon>
                                            </template><translate>
                                                This setting is for advanced use cases and will not normally be
                                                required. By default, Pexip Infinity matches against a parsed version
                                                of the destination alias, i.e. it ignores the URI scheme, any other
                                                parameters, and any host IP addresses. So, if the original alias is
                                            </translate>
                                            "sip:alice@example.com;transport=tls" for example, then by default the
                                            rule will match against "alice@example.com". Select this option to
                                            match against the full, unparsed alias instead.
                                        </v-tooltip>
                                    </template>
                                </v-checkbox>
                                <v-text-field
                                    v-model="form.match_string"
                                    :error-messages="errors.match_string ? errors.match_string : []"
                                    :rules="rules.match_string"
                                    clearable
                                    label="Destination alias regex match (*)"
                                    :counter="250"
                                >
                                    <template
                                        v-slot:append-outer
                                    >
                                        <v-tooltip
                                            left
                                            :max-width="420"
                                        >
                                            <template
                                                v-slot:activator="{ on, attrs }"
                                            >
                                                <v-icon
                                                    v-bind="attrs"
                                                    v-on="on"
                                                >
                                                    mdi-information
                                                </v-icon>
                                            </template><translate>The regular expression that the destination alias</translate> (the alias that was
                                            dialed) is checked against to see if this rule applies to this
                                            call.
                                        </v-tooltip>
                                    </template>
                                </v-text-field>
                                <v-text-field
                                    v-model="form.replace_string"
                                    :error-messages="errors.replace_string ? errors.replace_string : []"
                                    :rules="rules.replace_string"
                                    clearable
                                    :label="$gettext('Destination alias regex replace string')"
                                    :counter="250"
                                >
                                    <template
                                        v-slot:append-outer
                                    >
                                        <v-tooltip
                                            left
                                            :max-width="420"
                                        >
                                            <template
                                                v-slot:activator="{ on, attrs }"
                                            >
                                                <v-icon
                                                    v-bind="attrs"
                                                    v-on="on"
                                                >
                                                    mdi-information
                                                </v-icon>
                                            </template><translate>
                                                The regular expression string used to transform the originally dialed
                                                alias
                                            </translate> (if a match was found). Leave blank to leave the originally
                                            dialed alias unchanged.
                                        </v-tooltip>
                                    </template>
                                </v-text-field>
                            </v-card-text>
                        </v-card>
                    </v-tab-item>
                    <v-tab-item eager>
                        <v-card flat>
                            <v-card-text>
                                <v-select
                                    v-model="form.call_type"
                                    :error-messages="errors.call_type ? errors.call_type : []"
                                    :rules="rules.call_type"
                                    :label="$gettext('Call capability')"
                                    :items="choices.call_type"
                                    item-text="title"
                                    item-value="key"
                                >
                                    <template
                                        v-slot:append-outer
                                    >
                                        <v-tooltip
                                            left
                                            :max-width="420"
                                        >
                                            <template
                                                v-slot:activator="{ on, attrs }"
                                            >
                                                <v-icon
                                                    v-bind="attrs"
                                                    v-on="on"
                                                >
                                                    mdi-information
                                                </v-icon>
                                            </template><translate>
                                                Maximum media content of the call. The participant being called will
                                                not be able to escalate beyond the selected capability.
                                            </translate>
                                        </v-tooltip>
                                    </template>
                                </v-select>
                                <v-text-field
                                    v-model="form.max_callrate_in"
                                    type="number"
                                    :error-messages="errors.max_callrate_in ? errors.max_callrate_in : []"
                                    :rules="rules.max_callrate_in"
                                    label="Maximum inbound call bandwidth (kbps)"
                                >
                                    <template
                                        v-slot:append-outer
                                    >
                                        <v-tooltip
                                            left
                                            :max-width="420"
                                        >
                                            <template
                                                v-slot:activator="{ on, attrs }"
                                            >
                                                <v-icon
                                                    v-bind="attrs"
                                                    v-on="on"
                                                >
                                                    mdi-information
                                                </v-icon>
                                            </template><translate>
                                                This optional field allows you to limit the bandwidth of media being
                                                received by Pexip Infinity from each individual participant dialed in
                                                via this Call Routing Rule. Range: 128 to 8192.
                                            </translate>
                                        </v-tooltip>
                                    </template>
                                </v-text-field>
                                <v-text-field
                                    v-model="form.max_callrate_out"
                                    type="number"
                                    :error-messages="errors.max_callrate_out ? errors.max_callrate_out : []"
                                    :rules="rules.max_callrate_out"
                                    label="Maximum outbound call bandwidth (kbps)"
                                >
                                    <template
                                        v-slot:append-outer
                                    >
                                        <v-tooltip
                                            left
                                            :max-width="420"
                                        >
                                            <template
                                                v-slot:activator="{ on, attrs }"
                                            >
                                                <v-icon
                                                    v-bind="attrs"
                                                    v-on="on"
                                                >
                                                    mdi-information
                                                </v-icon>
                                            </template><translate>
                                                This optional field allows you to limit the bandwidth of media being
                                                sent by Pexip Infinity to each individual participant dialed out from
                                                this Call Routing Rule. Range: 128 to 8192.
                                            </translate>
                                        </v-tooltip>
                                    </template>
                                </v-text-field>
                                <v-select
                                    v-model="form.max_pixels_per_second"
                                    :error-messages="
                                        errors.max_pixels_per_second ? errors.max_pixels_per_second : []
                                    "
                                    :rules="rules.max_pixels_per_second"
                                    :label="$gettext('Maximum call quality')"
                                    :items="choices.max_pixels_per_second"
                                    item-text="title"
                                    item-value="key"
                                >
                                    <template
                                        v-slot:append-outer
                                    >
                                        <v-tooltip
                                            left
                                            :max-width="420"
                                        >
                                            <template
                                                v-slot:activator="{ on, attrs }"
                                            >
                                                <v-icon
                                                    v-bind="attrs"
                                                    v-on="on"
                                                >
                                                    mdi-information
                                                </v-icon>
                                            </template><translate>Sets the maximum call quality for each participant.</translate>
                                        </v-tooltip>
                                    </template>
                                </v-select>
                                <v-select
                                    v-model="form.crypto_mode"
                                    :error-messages="errors.crypto_mode ? errors.crypto_mode : []"
                                    :rules="rules.crypto_mode"
                                    :label="$gettext('Media encryption')"
                                    :items="choices.crypto_mode"
                                    item-text="title"
                                    item-value="key"
                                >
                                    <template
                                        v-slot:append-outer
                                    >
                                        <v-tooltip
                                            left
                                            :max-width="420"
                                        >
                                            <template
                                                v-slot:activator="{ on, attrs }"
                                            >
                                                <v-icon
                                                    v-bind="attrs"
                                                    v-on="on"
                                                >
                                                    mdi-information
                                                </v-icon>
                                            </template><translate>
                                                Controls the media encryption requirements for participants
                                                connecting to this service. Use global setting: Use the global media
                                                encryption setting
                                            </translate> (Platform > Global Settings). Required: All
                                            participants (including RTMP participants) must use media encryption.
                                            Best effort: Each participant will use media encryption if their
                                            device supports it, otherwise the connection will be unencrypted. No
                                            encryption: All H.323, SIP and MS-SIP participants must use
                                            unencrypted media. (RTMP participants will use encryption if their
                                            device supports it, otherwise the connection will be
                                            unencrypted.)
                                        </v-tooltip>
                                    </template>
                                </v-select>
                                <v-select
                                    v-model="form.ivr_theme"
                                    :error-messages="errors.ivr_theme ? errors.ivr_theme : []"
                                    :rules="rules.ivr_theme"
                                    :label="$gettext('Theme')"
                                    :items="ivr_themes"
                                    item-text="name"
                                    item-value="id"
                                >
                                    <template
                                        v-slot:append-outer
                                    >
                                        <v-tooltip
                                            left
                                            :max-width="420"
                                        >
                                            <template
                                                v-slot:activator="{ on, attrs }"
                                            >
                                                <v-icon
                                                    v-bind="attrs"
                                                    v-on="on"
                                                >
                                                    mdi-information
                                                </v-icon>
                                            </template><translate>
                                                The theme for use with this service. If no theme is selected here,
                                                files from the theme that has been selected as the default
                                            </translate> (Platform >
                                            Global settings > Default theme) will be applied.
                                        </v-tooltip>
                                    </template>
                                </v-select>
                            </v-card-text>
                        </v-card>
                    </v-tab-item>
                    <v-tab-item eager>
                        <v-card flat>
                            <v-card-text>
                                <v-select
                                    v-model="form.called_device_type"
                                    :error-messages="errors.called_device_type ? errors.called_device_type : []"
                                    :rules="rules.called_device_type"
                                    :label="$gettext('Call target')"
                                    :items="choices.called_device_type"
                                    item-text="title"
                                    item-value="key"
                                >
                                    <template
                                        v-slot:append-outer
                                    >
                                        <v-tooltip
                                            left
                                            :max-width="420"
                                        >
                                            <template
                                                v-slot:activator="{ on, attrs }"
                                            >
                                                <v-icon
                                                    v-bind="attrs"
                                                    v-on="on"
                                                >
                                                    mdi-information
                                                </v-icon>
                                            </template><translate>
                                                The device or system to which the call is routed. The options are:
                                                Registered device or external system: routes the call to a matching
                                                registered device if it is currently registered, otherwise attempts to
                                                route the call via an external system such as a SIP proxy, Lync /
                                                Skype for Business server, H.323 gatekeeper or other gateway/ITSP.
                                                Registered devices only: routes the call to a matching registered
                                                device only
                                            </translate> (providing it is currently registered). Lync / Skype for
                                            Business meeting direct (Conference ID in dialed alias): routes the
                                            call via a Lync / Skype for Business server to a Lync / Skype for
                                            Business meeting. Note that the destination alias must be transformed
                                            into just a Lync / Skype for Business Conference ID. Lync / Skype for
                                            Business clients, or meetings via a Virtual Reception: routes the call
                                            via a Lync / Skype for Business server either to a Lync / Skype for
                                            Business client, or - for calls that have come via a Virtual Reception
                                            - to a Lync / Skype for Business meeting. For Lync / Skype for
                                            Business meetings via Virtual Reception routing, ensure that Match
                                            against full alias URI is selected and that the Destination alias
                                            regex match ends with .*. Google Meet meeting: routes the call to a
                                            Google Meet meeting. Microsoft Teams meeting: routes the call to a
                                            Microsoft Teams meeting.
                                        </v-tooltip>
                                    </template>
                                </v-select>
                                <v-select
                                    v-model="form.outgoing_location"
                                    :error-messages="errors.outgoing_location ? errors.outgoing_location : []"
                                    :rules="rules.outgoing_location"
                                    :label="$gettext('Outgoing location')"
                                    clearable
                                    :items="outgoing_locations"
                                    item-text="name"
                                    item-value="id"
                                >
                                    <template
                                        v-slot:append-outer
                                    >
                                        <v-tooltip
                                            left
                                            :max-width="420"
                                        >
                                            <template
                                                v-slot:activator="{ on, attrs }"
                                            >
                                                <v-icon
                                                    v-bind="attrs"
                                                    v-on="on"
                                                >
                                                    mdi-information
                                                </v-icon>
                                            </template><translate>
                                                When calling an external system, this forces the outgoing call to be
                                                handled by a Conferencing Node in a specific location. When calling a
                                                Lync / Skype for Business meeting, a Conferencing Node in this
                                                location will handle the outgoing call, and - for
                                            </translate> 'Lync / Skype for
                                            Business meeting direct' targets - perform the Conference ID lookup on
                                            the Lync / Skype for Business server. Select Automatic to allow Pexip
                                            Infinity to automatically select which Conferencing Node to
                                            use.
                                        </v-tooltip>
                                    </template>
                                </v-select>
                                <v-select
                                    v-if="showFields.outgoing_protocol"
                                    v-model="form.outgoing_protocol"
                                    :error-messages="errors.outgoing_protocol ? errors.outgoing_protocol : []"
                                    :rules="rules.outgoing_protocol"
                                    :label="$gettext('Protocol')"
                                    clearable
                                    :items="choices.outgoing_protocol"
                                    item-text="title"
                                    item-value="key"
                                >
                                    <template
                                        v-slot:append-outer
                                    >
                                        <v-tooltip
                                            left
                                            :max-width="420"
                                        >
                                            <template
                                                v-slot:activator="{ on, attrs }"
                                            >
                                                <v-icon
                                                    v-bind="attrs"
                                                    v-on="on"
                                                >
                                                    mdi-information
                                                </v-icon>
                                            </template><translate>
                                                When calling an external system, this is the protocol to use when
                                                placing the outbound call. Note that if the call is to a registered
                                                device, Pexip Infinity will instead use the protocol that the device
                                                used to make the registration.
                                            </translate>
                                        </v-tooltip>
                                    </template>
                                </v-select>
                                <v-select
                                    v-if="showFields.sip_proxy"
                                    v-model="form.sip_proxy"
                                    :error-messages="errors.sip_proxy ? errors.sip_proxy : []"
                                    :rules="rules.sip_proxy"
                                    :label="$gettext('SIP proxy')"
                                    clearable
                                    :items="sip_proxys"
                                    item-text="name"
                                    item-value="id"
                                >
                                    <template
                                        v-slot:append-outer
                                    >
                                        <v-tooltip
                                            left
                                            :max-width="420"
                                        >
                                            <template
                                                v-slot:activator="{ on, attrs }"
                                            >
                                                <v-icon
                                                    v-bind="attrs"
                                                    v-on="on"
                                                >
                                                    mdi-information
                                                </v-icon>
                                            </template><translate>
                                                When calling an external system, this is the SIP proxy to use for
                                                outbound SIP calls. Select Use DNS to try to use normal SIP resolution
                                                procedures to route the call.
                                            </translate>
                                        </v-tooltip>
                                    </template>
                                </v-select>
                                <v-select
                                    v-if="showFields.teams_proxy"
                                    v-model="form.teams_proxy"
                                    :error-messages="errors.teams_proxy ? errors.teams_proxy : []"
                                    :rules="rules.teams_proxy"
                                    :label="$gettext('Teams Connector')"
                                    :items="teams_proxys"
                                    item-text="name"
                                    item-value="id"
                                    clearable
                                >
                                    <template
                                        v-slot:append-outer
                                    >
                                        <v-icon class="mr-1">
                                            mdi-plus
                                        </v-icon>
                                        <v-tooltip
                                            left
                                            :max-width="420"
                                        >
                                            <template
                                                v-slot:activator="{ on, attrs }"
                                            >
                                                <v-icon
                                                    v-bind="attrs"
                                                    v-on="on"
                                                >
                                                    mdi-information
                                                </v-icon>
                                            </template><translate>
                                                The Teams Connector to use for the Teams meeting. If you do not
                                                specify anything, the Teams Connector associated with the outgoing
                                                location is used.
                                            </translate>
                                        </v-tooltip>
                                    </template>
                                </v-select>
                                <v-select
                                    v-if="showFields.gms_access_token"
                                    v-model="form.gms_access_token"
                                    :error-messages="errors.gms_access_token ? errors.gms_access_token : []"
                                    :rules="rules.gms_access_token"
                                    :label="$gettext('Access token')"
                                    clearable
                                    :items="gms_access_tokens"
                                    item-text="name"
                                    item-value="id"
                                >
                                    <template
                                        v-slot:append-outer
                                    >
                                        <v-tooltip
                                            left
                                            :max-width="420"
                                        >
                                            <template
                                                v-slot:activator="{ on, attrs }"
                                            >
                                                <v-icon
                                                    v-bind="attrs"
                                                    v-on="on"
                                                >
                                                    mdi-information
                                                </v-icon>
                                            </template><translate>
                                                The access token to use when resolving Google Meet meeting
                                                codes.
                                            </translate>
                                        </v-tooltip>
                                    </template>
                                </v-select>
                                <v-select
                                    v-if="showFields.h323_gatekeeper"
                                    v-model="form.h323_gatekeeper"
                                    :error-messages="errors.h323_gatekeeper ? errors.h323_gatekeeper : []"
                                    :rules="rules.h323_gatekeeper"
                                    :label="$gettext('H.323 gatekeeper')"
                                    clearable
                                    :items="h323_gatekeepers"
                                    item-text="name"
                                    item-value="id"
                                >
                                    <template
                                        v-slot:append-outer
                                    >
                                        <v-tooltip
                                            left
                                            :max-width="420"
                                        >
                                            <template
                                                v-slot:activator="{ on, attrs }"
                                            >
                                                <v-icon
                                                    v-bind="attrs"
                                                    v-on="on"
                                                >
                                                    mdi-information
                                                </v-icon>
                                            </template><translate>
                                                When calling an external system, this is the H.323 gatekeeper to use
                                                for outbound H.323 calls. Select Use DNS to try to use normal H.323
                                                resolution procedures to route the call.
                                            </translate>
                                        </v-tooltip>
                                    </template>
                                </v-select>
                                <v-select
                                    v-if="showFields.mssip_proxy"
                                    v-model="form.mssip_proxy"
                                    :error-messages="errors.mssip_proxy ? errors.mssip_proxy : []"
                                    :rules="rules.mssip_proxy"
                                    :label="$gettext('Lync / Skype for Business server')"
                                    clearable
                                    :items="mssip_proxys"
                                    item-text="name"
                                    item-value="id"
                                >
                                    <template
                                        v-slot:append-outer
                                    >
                                        <v-tooltip
                                            left
                                            :max-width="420"
                                        >
                                            <template
                                                v-slot:activator="{ on, attrs }"
                                            >
                                                <v-icon
                                                    v-bind="attrs"
                                                    v-on="on"
                                                >
                                                    mdi-information
                                                </v-icon>
                                            </template><translate>
                                                When calling an external system, this is the Lync / Skype for
                                                Business server to use for outbound Lync / Skype for Business
                                            </translate> (MS-SIP)
                                            calls. Select Use DNS to try to use normal Lync / Skype for Business
                                            (MS-SIP) resolution procedures to route the call. When calling a Lync
                                            / Skype for Business meeting, this is the Lync / Skype for Business
                                            server to use for the Conference ID lookup and to place the
                                            call.
                                        </v-tooltip>
                                    </template>
                                </v-select>
                                <v-select
                                    v-if="showFields.stun_server"
                                    v-model="form.stun_server"
                                    :error-messages="errors.stun_server ? errors.stun_server : []"
                                    :rules="rules.stun_server"
                                    :label="$gettext('STUN server')"
                                    clearable
                                    :items="stun_servers"
                                    item-text="name"
                                    item-value="id"
                                >
                                    <template
                                        v-slot:append-outer
                                    >
                                        <v-tooltip
                                            left
                                            :max-width="420"
                                        >
                                            <template
                                                v-slot:activator="{ on, attrs }"
                                            >
                                                <v-icon
                                                    v-bind="attrs"
                                                    v-on="on"
                                                >
                                                    mdi-information
                                                </v-icon>
                                            </template><translate>The STUN server to be used for outbound Lync / Skype for Business</translate>
                                            (MS-SIP) calls (where applicable).
                                        </v-tooltip>
                                    </template>
                                </v-select>
                                <v-select
                                    v-if="showFields.turn_server"
                                    v-model="form.turn_server"
                                    :error-messages="errors.turn_server ? errors.turn_server : []"
                                    :rules="rules.turn_server"
                                    :label="$gettext('TURN server')"
                                    clearable
                                    :items="turn_servers"
                                    item-text="name"
                                    item-value="id"
                                >
                                    <template
                                        v-slot:append-outer
                                    >
                                        <v-tooltip
                                            left
                                            :max-width="420"
                                        >
                                            <template
                                                v-slot:activator="{ on, attrs }"
                                            >
                                                <v-icon
                                                    v-bind="attrs"
                                                    v-on="on"
                                                >
                                                    mdi-information
                                                </v-icon>
                                            </template><translate>The TURN server to be used for outbound Lync / Skype for Business</translate>
                                            (MS-SIP) calls (where applicable).
                                        </v-tooltip>
                                    </template>
                                </v-select>
                                <v-select
                                    v-if="showFields.external_participant_avatar_lookup"
                                    v-model="form.external_participant_avatar_lookup"
                                    :error-messages="
                                        errors.external_participant_avatar_lookup
                                            ? errors.external_participant_avatar_lookup
                                            : []
                                    "
                                    :rules="rules.external_participant_avatar_lookup"
                                    :label="$gettext('External participant avatar lookup')"
                                    clearable
                                    :items="choices.external_participant_avatar_lookup"
                                    item-text="title"
                                    item-value="key"
                                >
                                    <template
                                        v-slot:append-outer
                                    >
                                        <v-tooltip
                                            left
                                            :max-width="420"
                                        >
                                            <template
                                                v-slot:activator="{ on, attrs }"
                                            >
                                                <v-icon
                                                    v-bind="attrs"
                                                    v-on="on"
                                                >
                                                    mdi-information
                                                </v-icon>
                                            </template><translate>
                                                Determines whether or not avatars for external participants will be
                                                retrieved using the method appropriate for the external meeting type.
                                                You can use this option to override the global configuration
                                                setting.
                                            </translate>
                                        </v-tooltip>
                                    </template>
                                </v-select>

                                <v-checkbox
                                    v-model="form.treat_as_trusted"
                                    :error-messages="
                                        errors.treat_as_trusted ? errors.treat_as_trusted : []
                                    "
                                    :rules="rules.treat_as_trusted"
                                    :label="$gettext('Treat as trusted')"
                                    class="mt-2"
                                >
                                    <template v-slot:append>
                                        <v-tooltip
                                            left
                                            :max-width="420"
                                        >
                                            <template v-slot:activator="{ on, attrs }">
                                                <v-icon
                                                    v-bind="attrs"
                                                    v-on="on"
                                                >
                                                    mdi-information
                                                </v-icon>
                                            </template>
                                            <translate>
                                                This indicates the target of this routing rule will treat the caller as
                                                part of the target organization for trust purposes.
                                            </translate>
                                        </v-tooltip>
                                    </template>
                                </v-checkbox>
                            </v-card-text>
                        </v-card>
                    </v-tab-item>
                </v-tabs-items>
            </v-card-text>
            <v-divider />
            <v-alert
                v-if="error || (hasSubmitted && !formValid)"
                tile
                type="error"
            >
                <ErrorMessage
                    v-if="error"
                    :error="error"
                />
                <template v-else>
                    {{ $gettext('Det finns fel i formuläret') }}
                </template>
            </v-alert>
            <v-card-actions>
                <v-btn
                    v-if="id || tab >= 3"
                    :loading="formLoading"
                    color="primary"
                    type="submit"
                    @click="hasSubmitted = true"
                >
                    {{ buttonText }}
                </v-btn>
                <v-btn
                    v-else
                    :loading="formLoading"
                    color="primary"
                    @click.prevent="tab ++"
                >
                    <translate>Nästa</translate>
                </v-btn>

                <v-spacer />

                <v-btn
                    v-if="id"
                    class="mr-2"
                    color="primary"
                    :to="{ name: 'policy_rules', query: { copy: id } }"
                    @click.native="$emit('copy')"
                >
                    <translate>Kopiera</translate>
                </v-btn>
                <v-btn-confirm
                    v-if="id"
                    color="error"
                    :bind="{class: 'ml-2'}"
                    @click="remove"
                >
                    <translate>Radera</translate>
                </v-btn-confirm>

                <v-btn
                    v-close-dialog
                    class="ml-2"
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
    </v-form>
</template>

<script>
import { $gettext } from '@/vue/helpers/translate'

import { closeDialog } from '@/vue/helpers/dialog'
import VBtnConfirm from '@/vue/components/VBtnConfirm'
import ErrorMessage from '@/vue/components/base/ErrorMessage'

function getResetErrorWatchers(fields) {
    const result = {}
    Array.from(fields.pop ? fields : arguments).forEach(
        f =>
            (result['form.' + f] = function() {
                this.$set(this.errors, f, null)
            })
    )
    return result
}
// eslint-disable-next-line max-lines-per-function
function emptyForm(initialData = null) {
    return {
        enable: true,
        sync_back: true,
        is_fallback: false,
        name: '',
        tag: '',
        description: '',
        priority: 10,
        match_incoming_calls: false,
        match_outgoing_calls: false,
        match_source_location: null,
        match_source_alias: '',
        match_source_mode: 'AND',
        match_incoming_only_if_registered: false,
        match_incoming_webrtc: false,
        match_incoming_sip: false,
        match_incoming_mssip: false,
        match_incoming_h323: false,
        match_string_full: false,
        match_string: '',
        replace_string: '',
        call_type: 'auto',
        max_callrate_in: null,
        max_callrate_out: null,
        max_pixels_per_second: null,
        crypto_mode: '',
        ivr_theme: null,
        called_device_type: 'external',
        outgoing_location: null,
        outgoing_protocol: 'sip',
        sip_proxy: null,
        teams_proxy: null,
        gms_access_token: null,
        h323_gatekeeper: null,
        mssip_proxy: null,
        stun_server: null,
        turn_server: null,
        external_participant_avatar_lookup: 'default',
        treat_as_trusted: false,
        ...(initialData || {}),
    }
}
export default {
    components: { ErrorMessage, VBtnConfirm },
    props: {
        id: { type: Number, required: false, default: null },
        initialData: { type: Object, required: false, default() { return {} }},
        buttonText: { type: String, required: false, default: $gettext('Spara') },
        provider: { type: Number, required: false, default: undefined },
    },
    data() {
        return {
            tab: 0,
            loading: false,
            error: '',
            formLoading: false,
            formValid: false,
            form: emptyForm(this.initialData),
            rules: this.getRules(),
            choices: this.getChoices(),
            errors: {},
            hasSubmitted: false,
        }
    },
    computed: {
        relatedObjects() {
            return this.$store.state.policy_rule.related
        },
        match_source_locations() {
            return Object.values(this.relatedObjects.system_location || {})
        },
        ivr_themes() {
            return Object.values(this.relatedObjects.ivr_theme || {})
        },
        outgoing_locations() {
            return Object.values(this.relatedObjects.system_location || {})
        },
        sip_proxys() {
            return Object.values(this.relatedObjects.sip_proxy || {})
        },
        teams_proxys() {
            return Object.values(this.relatedObjects.teams_proxy || {})
        },
        gms_access_tokens() {
            return Object.values(this.relatedObjects.gms_access_token || {})
        },
        h323_gatekeepers() {
            return Object.values(this.relatedObjects.h323_gatekeeper || {})
        },
        mssip_proxys() {
            return Object.values(this.relatedObjects.mssip_proxy || {})
        },
        stun_servers() {
            return Object.values(this.relatedObjects.stun_server || {})
        },
        turn_servers() {
            return Object.values(this.relatedObjects.turn_server || {})
        },
        providers() {
            return Object.values(this.$store.state.provider.providers || {})
        },
        // eslint-disable-next-line max-lines-per-function
        showFields() {
            const result = {
                external_participant_avatar_lookup: false,
                gms_access_token: false,
                h323_gatekeeper: false,
                mssip_proxy: false,
                sip_proxy: false,
                stun_server: false,
                teams_proxy: false,
                treat_as_trusted: false,
                turn_server: false,
                outgoing_location: false,
                outgoing_protocol: false,
                called_device_type: true,
            }
            const toggle = (fields, value=true) => (fields || []).forEach(f => result[f] = value)
            toggle({
                gms: ['turn_server', 'stun_server', 'gms_access_token', 'treat_as_trusted'],
                h323: ['h323_gatekeeper'],
                mssip: ['mssip_proxy', 'turn_server', 'stun_server'],
                sip: ['treat_as_trusted', 'sip_proxy'],
                teams: ['teams_proxy', 'treat_as_trusted', 'external_participant_avatar_lookup']
            }[this.form.outgoing_protocol])

            if (this.form.outgoing_protocol === 'rtmp') {
                toggle(['called_device_type'], false)
            }

            toggle({
                external: ['outgoing_location', 'outgoing_protocol'],
                registration: ['treat_as_trusted'],
                mssip_conference_id: ['mssip_proxy', 'turn_server', 'stun_server'],
                mssip_server: ['mssip_proxy', 'turn_server', 'stun_server'],
                gms_conference: ['outgoing_location', 'turn_server', 'stun_server', 'treat_as_trusted', 'gms_access_token'],
                teams_conference: ['teams_proxy', 'treat_as_trusted', 'outgoing_location', 'external_participant_avatar_lookup'],
                teams_user: ['teams_proxy', 'treat_as_trusted', 'outgoing_location', 'external_participant_avatar_lookup'],
            }[this.form.called_device_type])

            return result
        },
        policy_rules() {
            return Object.values(this.$store.state.policy_rule.rules)
        },
    },
    watch: {
        ...getResetErrorWatchers(...Object.keys(emptyForm())),
        id() {
            this.init()
        },
    },
    created() {
        this.init()
    },
    methods: {
        // eslint-disable-next-line max-lines-per-function
        getRules() {
            const required = v => !!v || $gettext('Värdet måste fyllas i')
            const checkIntRequired = v => !isNaN(parseInt(v)) || $gettext('Värdet måste vara ett tal')
            const checkInt = v => (!v && v !== 0) || !isNaN(parseInt(v)) || $gettext('Värdet måste vara ett tal')

            const checkIncoming = (v) => {
                if (v && !['match_source_alias', 'match_incoming_webrtc', 'match_incoming_sip', 'match_incoming_mssip', 'match_incoming_h323'].some(x => !!this.form[x])) {
                    return 'Du måste välja minst en typ av inkommande trafik att matcha'
                }
                return true
            }

            const checkDuplicateName = () => {
                const existing = this.policy_rules.find(r => r.name.toLowerCase() === this.form.name.toLowerCase())
                if (existing && existing.id !== this.id) {
                    return 'Det finns redan en regel med det här namnet'
                }
                return true
            }
            const checkDuplicatePriority = () => {
                if (!this.form.sync_back) return true

                const existing = this.policy_rules.find(r => r.priority === this.form.priority && r.sync_back)
                if (existing && existing.id !== this.id) {
                    return 'Det finns redan en regel med samma prioritet som synkroniseras'
                }
                return true
            }

            return {
                id: [checkInt],
                name: [required, checkDuplicateName],
                priority: [checkIntRequired, checkDuplicatePriority],
                match_string: [required],
                max_callrate_in: [checkInt],
                max_callrate_out: [checkInt],
                cluster: [required],
                match_incoming_webrtc: [checkIncoming],
            }
        },
        // eslint-disable-next-line max-lines-per-function
        getChoices() {
            return {
                call_type: [
                    { key: 'audio', title: $gettext('Audio only') },
                    { key: 'video', title: 'Main video + presentation' },
                    { key: 'video-only', title: $gettext('Main video only') },
                    { key: 'auto', title: $gettext('Same as incoming call') },
                ],
                max_pixels_per_second: [
                    { key: null, title: $gettext('Default') },
                    { key: 'sd', title: 'sd' },
                    { key: 'hd', title: 'hd' },
                    { key: 'fullhd', title: 'fullhd' },
                ],
                crypto_mode: [
                    { key: '', title: $gettext('Default') },
                    { key: 'besteffort', title: 'besteffort' },
                    { key: 'on', title: 'on' },
                    { key: 'off', title: 'off' },
                ],
                called_device_type: [
                    { key: 'external', title: $gettext('Registered device or external system') },
                    { key: 'registration', title: $gettext('Registered devices only') },
                    {
                        key: 'mssip_conference_id',
                        title: 'Lync / Skype for Business meeting direct (Conference ID in dialed alias)',
                    },
                    {
                        key: 'mssip_server',
                        title: $gettext('Lync / Skype for Business clients, or meetings via a Virtual Reception'),
                    },
                    { key: 'gms_conference', title: $gettext('Google Meet meeting') },
                    { key: 'teams_conference', title: $gettext('Microsoft Teams meeting') },
                ],
                match_source_mode: [
                    { key: 'AND', text: $gettext('Source Alias AND Location must match') },
                    { key: 'OR', text: $gettext('Source Alias OR Location must match') },
                ],
                outgoing_protocol: [
                    { key: 'h323', title: $gettext('h323') },
                    { key: 'mssip', title: 'mssip' },
                    { key: 'sip', title: 'sip' },
                    { key: 'rtmp', title: 'rtmp' },
                    { key: 'gms', title: 'gms' },
                    { key: 'teams', title: 'teams' },
                ],
                external_participant_avatar_lookup: [
                    { key: 'default', title: 'default' },
                    { key: 'yes', title: 'yes' },
                    { key: 'no', title: 'no' },
                ],
            }
        },
        submit() {
            if (!this.$refs.form.validate()) return
            this.formLoading = true
            const { id } = this
            this.error = null

            const action = !id
                ? this.$store.dispatch('policy_rule/createPolicyRule', { ...this.form, provider: this.provider })
                : this.$store.dispatch('policy_rule/updatePolicyRule', { id, data: this.form, provider: this.provider })
            action
                .then(() => {
                    this.formLoading = false
                    this.errors = {}
                    closeDialog(this)
                })
                .catch(e => {
                    this.formLoading = false
                    if (e.errors) {
                        this.errors = e.errors
                        if (e.errors.__all__) {
                            this.error = e.errors.__all__
                        }
                    } else {
                        this.error = e
                    }
                })
        },
        async remove() {
            await this.$store.dispatch('policy_rule/deletePolicyRule', { id: this.id, provider: this.provider })
            closeDialog(this)
        },
        init() {
            this.loading = true
            this.error = null
            return Promise.all([
                this.id
                    ? this.$store.dispatch('policy_rule/getPolicyRule', { id: this.id, provider: this.provider })
                    : Promise.resolve(this.initialData || {}),
                this.$store.dispatch('policy_rule/getRelatedObjects', { provider: this.provider }),
                //this.$store.dispatch('provider/getProviders'),
            ]).then(values => {
                this.form = { ...this.form, ...values[0] }
                this.loading = false
            }).catch(e => {
                this.error = e
            })
        },
    },
}
</script>
