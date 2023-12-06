<template>
    <v-card>
        <v-card-title><translate>Powershell-kommandon</translate></v-card-title>
        <v-card-text>
            <translate>
                Du kan ändra så kalenderinformation sparas genom att köra något av de följande kommandona i PowerShell.
                Läs mer om Set-CalendarProcessing och vad respektive kommando innebär här:
            </translate>
            <a href="https://docs.microsoft.com/en-us/powershell/module/exchange/set-calendarprocessing?view=exchange-ps">docs.microsoft.com</a>
        </v-card-text>
        <v-divider />
        <v-card-text class="pt-4">
            <v-expansion-panels>
                <v-expansion-panel>
                    <v-expansion-panel-header>
                        <translate>Installera modul och logga in till Exchange Online</translate>
                    </v-expansion-panel-header>
                    <v-expansion-panel-content>
                        <v-textarea
                            filled
                            hide-details
                            rows="3"
                            class="v-textarea--code"
                            :value="`
Install-Module -Name ExchangeOnlineManagement
Connect-ExchangeOnline
`.trim()"
                        />
                    </v-expansion-panel-content>
                </v-expansion-panel>
                <v-expansion-panel>
                    <v-expansion-panel-header>
                        <translate>Spara inbjudningsinformation i alla befintliga rumsresursers kalendrar</translate>
                    </v-expansion-panel-header>
                    <v-expansion-panel-content>
                        <v-textarea
                            filled
                            rows="3"
                            class="v-textarea--code"
                            :value="`
$ConfRooms = Get-Mailbox -RecipientTypeDetails RoomMailbox | select -ExpandProperty Alias
$ConfRooms | Set-CalendarProcessing -DeleteComments $false -DeleteSubject $false -RemovePrivateProperty $false -AddOrganizerToSubject $false -ProcessExternalMeetingMessages $true
`.trim()"
                        />
                        <v-alert
                            border="left"
                            text
                            dense
                            type="info"
                            class="text-caption"
                        >
                            <translate>Detta kommando kräver administratörsrättigheter</translate>.
                        </v-alert>
                    </v-expansion-panel-content>
                </v-expansion-panel>
                <v-expansion-panel>
                    <v-expansion-panel-header>
                        <translate>Spara inbjudningsinformation i en enskild rumsresursers kalender</translate>
                    </v-expansion-panel-header>
                    <v-expansion-panel-content>
                        <v-textarea
                            filled
                            rows="2"
                            class="v-textarea--code"
                            :value="`
Set-CalendarProcessing -Identity exampleroom@example.org -DeleteComments $false -DeleteSubject $false -RemovePrivateProperty $false -AddOrganizerToSubject $false -ProcessExternalMeetingMessages $true
`.trim()"
                        />
                        <v-alert
                            border="left"
                            text
                            dense
                            type="info"
                            class="text-caption"
                        >
                            <translate>Detta kommando kräver administratörsrättigheter</translate>.
                            <translate>Byt ut exampleroom@example.org med adressen till din rumsresurs</translate>.
                        </v-alert>
                    </v-expansion-panel-content>
                </v-expansion-panel>
                <v-expansion-panel>
                    <v-expansion-panel-header>
                        <translate>
                            EWS - lägg till en distributionsgrupp för att automatiskt hämta alla tillgängliga resurser
                        </translate>
                    </v-expansion-panel-header>
                    <v-expansion-panel-content>
                        <v-textarea
                            filled
                            rows="4"
                            class="v-textarea--code"
                            :value="`
New-DistributionGroup -Name &quot;Conference Rooms&quot; -PrimarySmtpAddress &quot;allrooms@example.org&quot; -RoomList
$ConfRooms = Get-Mailbox -RecipientTypeDetails RoomMailbox | select -ExpandProperty Alias
$ConfRooms | Add-DistributionGroupMember -Identity &quot;Conference Rooms&quot;
`.trim()"
                        />
                        <v-alert
                            border="left"
                            text
                            dense
                            type="info"
                            class="text-caption"
                        >
                            <translate>Detta kommando kräver administratörsrättigheter</translate>.
                            <translate>Byt ut "Conference Rooms" till namnet på den nya listan, och allrooms@example.org med dess e-postadress</translate>.
                        </v-alert>
                    </v-expansion-panel-content>
                </v-expansion-panel>
            </v-expansion-panels>
        </v-card-text>
    </v-card>
</template>
<script>
export default {
    name: 'CalendarPowerShellInstructions'
}
</script>
