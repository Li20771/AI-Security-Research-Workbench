import { deepFreeze } from "../canonical-json.ts";
import type { PluginRef } from "../contract.ts";

export type PluginSideEffects = "none" | "read-only" | "execute";

export interface PluginDefinition extends PluginRef {
  side_effects: PluginSideEffects;
}

export const PLUGIN_REGISTRY: readonly PluginDefinition[] = deepFreeze([
  {
    plugin_id: "fleet.core",
    version: "1.0.0",
    enabled: true,
    side_effects: "none"
  },
  {
    plugin_id: "fleet.output-schema",
    version: "1.0.0",
    enabled: true,
    side_effects: "none"
  },
  {
    plugin_id: "fleet.ledger",
    version: "1.0.0",
    enabled: true,
    side_effects: "none"
  },
  {
    plugin_id: "fleet.memorypack-readonly",
    version: "1.0.0",
    enabled: true,
    side_effects: "read-only"
  },
  {
    plugin_id: "fleet.securitylab-ro",
    version: "1.0.0",
    enabled: true,
    side_effects: "read-only"
  },
  {
    plugin_id: "fleet.securitylab-vcan",
    version: "1.0.0",
    enabled: false,
    side_effects: "execute"
  }
]);

const PLUGIN_MAP = new Map(PLUGIN_REGISTRY.map((plugin) => [plugin.plugin_id, plugin]));

export function getPlugin(pluginId: string): PluginDefinition | undefined {
  return PLUGIN_MAP.get(pluginId);
}

export function pluginRef(pluginId: string, enabled: boolean = true): PluginRef {
  return { plugin_id: pluginId, version: "1.0.0", enabled };
}

export interface PluginValidationResult {
  ok: boolean;
  code: "plugin-unregistered" | "plugin-disabled" | null;
  plugin_id: string | null;
  message: string | null;
}

export function validatePluginManifest(
  manifest: readonly PluginRef[]
): PluginValidationResult {
  for (const ref of manifest) {
    const registered = getPlugin(ref.plugin_id);
    if (registered === undefined || registered.version !== ref.version) {
      return {
        ok: false,
        code: "plugin-unregistered",
        plugin_id: ref.plugin_id,
        message: `plugin is not registered at the requested version: ${ref.plugin_id}`
      };
    }
    if (!registered.enabled || !ref.enabled) {
      return {
        ok: false,
        code: "plugin-disabled",
        plugin_id: ref.plugin_id,
        message: `plugin is disabled: ${ref.plugin_id}`
      };
    }
  }
  return { ok: true, code: null, plugin_id: null, message: null };
}
