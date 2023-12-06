<template>
    <div>
        <v-simple-table
            v-if="isRoot"
            class="mt-5"
        >
            <thead>
                <tr>
                    <th
                        v-translate
                        class="text-left grey-lighten-4"
                    >
                        Option
                    </th>
                    <th
                        v-translate
                        class="text-right"
                    >
                        Värde just nu
                    </th>
                </tr>
            </thead>
        </v-simple-table>

        <v-simple-table v-if="nodes.optionNodes.length">
            <template v-slot:default>
                <tbody>
                    <template v-for="node in nodes.optionNodes">
                        <ConfigurationWrapper
                            :key="node.title + node.options.index"
                            :endpoint-id="endpointId"
                            :setting="node.setting"
                        />
                    </template>
                </tbody>
            </template>
        </v-simple-table>

        <div
            v-for="node in nodes.groupNodes"
            :key="node.key + 'group'"
        >
            <div
                v-if="node.extender"
                :class="{ 'mx-4': node.depth > 1 }"
            >
                <v-expansion-panels
                    accordion
                    multiple
                    :value="[0]"
                    class="mb-3"
                >
                    <v-expansion-panel>
                        <v-expansion-panel-header>
                            <strong>
                                <span v-if="node.parent && node.parent.parent">{{ node.parent.parent.title }} - </span>
                                <span v-if="node.parent">{{ node.parent.title }} - </span>
                                {{ node.title }}
                                {{ node.options.index > 0 ? node.options.index + 1 : '' }}
                            </strong>
                        </v-expansion-panel-header>
                        <v-expansion-panel-content class="px-0">
                            <ConfigurationTree
                                :endpoint-id="endpointId"
                                :tree="node.children"
                                :filter="filter"
                                :depth="depth + 1"
                                :parent="node"
                            />
                        </v-expansion-panel-content>
                    </v-expansion-panel>
                </v-expansion-panels>
            </div>
            <div v-else>
                <v-simple-table :key="node.title + node.options.index">
                    <template v-slot:default>
                        <thead>
                            <tr>
                                <th class="text-left grey-lighten-4 primary--text">
                                    <span v-if="node.parent && node.parent.parent">{{ node.parent.parent.title }} - </span>
                                    <span v-if="node.parent">{{ node.parent.title }} - </span>
                                    <strong>
                                        {{ node.title }}
                                        {{ node.options.index > 0 ? node.options.index + 1 : '' }}
                                    </strong>
                                </th>
                            </tr>
                        </thead>
                    </template>
                </v-simple-table>
                <ConfigurationTree
                    :endpoint-id="endpointId"
                    :tree="node.children"
                    :filter="filter"
                    :depth="depth + 1"
                    :parent="node"
                />
            </div>
        </div>

        <div
            v-for="node in nodes.containerNodes"
            :key="node.key + 'container'"
        >
            <div v-if="node.root && node.childrenContainerNodes.length === 0">
                <ConfigurationTree
                    :endpoint-id="endpointId"
                    :tree="node.children"
                    :filter="filter"
                    :depth="depth + 1"
                    :parent="node"
                />
            </div>
            <div v-else>
                <div
                    class="mb-4"
                    :class="{
                        'mx-4':
                            node.depth > 0 &&
                            node.parent.childrenContainerNodes &&
                            node.parent.childrenContainerNodes.length !== 0,
                    }"
                >
                    <v-expansion-panels
                        accordion
                        multiple
                        :value="[0]"
                    >
                        <v-expansion-panel>
                            <v-expansion-panel-header>
                                <strong>
                                    <span v-if="node.parent && node.parent.parent">{{ node.parent.parent.title }} - </span>
                                    <span v-if="node.parent">{{ node.parent.title }} - </span>
                                    {{ node.title }}
                                    {{ node.options.index > 0 ? node.options.index + 1 : '' }}
                                </strong>
                            </v-expansion-panel-header>
                            <v-expansion-panel-content class="px-0">
                                <ConfigurationTree
                                    :endpoint-id="endpointId"
                                    :tree="node.children"
                                    :filter="filter"
                                    :depth="depth + 1"
                                    :parent="node"
                                />
                            </v-expansion-panel-content>
                        </v-expansion-panel>
                    </v-expansion-panels>
                </div>
            </div>
        </div>
    </div>
</template>

<script>
import { filterNodes, filterNodesSorting } from '@/vue/helpers/tree'

import ConfigurationWrapper from './ConfigurationWrapper'

export default {
    name: 'ConfigurationTree',
    components: { ConfigurationWrapper },
    props: {
        tree: { type: Array, default() { return [] } },
        isRoot: { type: Boolean, default: false },
        endpointId: { type: Number, default: null },
        filter: { type: String, default: '' },
        parent: {
            type: Object,
            default: null,
        },
        depth: { type: Number, default: 0 },
    },
    computed: {
        nodes() {
            return this.settingObjects(this.tree)
        },
    },
    methods: {
        getCommands(node) {
            return Object.values(node).filter(n => n.is_command)
        },
        settingObjects(nodes) {
            const filtered = filterNodes(this.filter, nodes).map(node => {
                const [title, options, children, setting] = node

                const childrenOptionNodes = children.filter(node => node[2].length === 0)
                const childrenGroupNodes = children.filter(node => node[2].length > 0)
                const childrenContainerNodes = children.filter(
                    node => node[2].filter(childNode => childNode[2].length === 0).length > 0
                )

                const extender =
                    this.depth === 1 && this.parent.childrenOptionNodes.length > 0 && !this.isRoot

                return {
                    title,
                    setting,
                    options,
                    children,

                    childrenOptionNodes,
                    childrenGroupNodes,
                    childrenContainerNodes,

                    extender,

                    depth: this.depth,
                    parent: this.parent,
                    root: this.isRoot,
                    orig: node,
                    key: options.path.join('>'),
                }
            })

            if (this.isRoot) {
                filtered.sort(filterNodesSorting)
            }

            return this.settingResults(filtered)
        },
        settingResults(filtered) {
            const result = {
                optionNodes: [],
                containerNodes: [],
                groupNodes: [],
            }
            filtered.forEach(node => {
                if (node.setting) {
                    return result.optionNodes.push(node)
                }

                let found = false
                node.children.map(childNode => {
                    if (!found && childNode[2].length === 0) {
                        found = true
                    }
                })

                result[found ? 'groupNodes' : 'containerNodes'].push(node)
            })

            return {
                nodes: filtered,
                ...result,
            }
        }
    },
}
</script>
