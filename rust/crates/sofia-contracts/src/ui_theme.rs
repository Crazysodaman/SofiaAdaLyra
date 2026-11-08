//! Shared, versioned presentation-only Aegis GUI/TUI color contract.
//! No service authority, state mutation, or Core-dependent theme logic.

use crate::{parse_strict, ContractError};
use serde::Deserialize;
use std::collections::BTreeMap;

pub const UI_THEME_SCHEMA: &str = "aegis.ui.theme.v1";
pub const DEFAULT_THEME_NAME: &str = "aegis-dark";
pub const BUNDLED_THEME: &str = include_str!("../../../../contracts/ui/aegis-theme-v1.json");

/// The sole trusted palette definition consumed by native GUI/TUI code.
/// Values are presentation tokens only and must never imply service health.
#[derive(Debug, Clone, PartialEq, Eq, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct UiTheme {
    pub schema: String,
    pub name: String,
    pub tokens: BTreeMap<String, String>,
}

impl UiTheme {
    /// Parse a bounded, strict theme document with the exact reviewed token set.
    ///
    /// # Errors
    /// Rejects duplicate keys, unknown/missing roles, malformed colors, and
    /// unsupported schemas. Color parsing never grants execution authority.
    pub fn parse(raw: &[u8]) -> Result<Self, ContractError> {
        const REQUIRED: [&str; 22] = [
            "accent",
            "background",
            "button_primary",
            "danger",
            "error",
            "glow",
            "highlight_bright",
            "hover",
            "hud_primary",
            "hud_secondary",
            "indicator",
            "primary",
            "success",
            "surface_card",
            "tertiary",
            "tertiary_dark",
            "text_main",
            "text_muted",
            "text_on_background_brand",
            "text_on_primary",
            "visr",
            "warning",
        ];
        let value = parse_strict(raw)?;
        let theme: Self = serde_json::from_value(value)
            .map_err(|error| ContractError::new("invalid_ui_theme", error.to_string()))?;
        if theme.schema != UI_THEME_SCHEMA || theme.name != DEFAULT_THEME_NAME {
            return Err(ContractError::new(
                "invalid_ui_theme",
                "unknown theme schema or name",
            ));
        }
        if theme.tokens.len() != REQUIRED.len()
            || REQUIRED
                .iter()
                .any(|role| !theme.tokens.contains_key(*role))
        {
            return Err(ContractError::new(
                "invalid_ui_theme",
                "unknown or missing presentation token",
            ));
        }
        for color in theme.tokens.values() {
            let bytes = color.as_bytes();
            if bytes.len() != 7
                || bytes[0] != b'#'
                || !bytes[1..]
                    .iter()
                    .all(|byte| byte.is_ascii_hexdigit() && !byte.is_ascii_lowercase())
            {
                return Err(ContractError::new(
                    "invalid_ui_theme",
                    "expected uppercase #RRGGBB sRGB token",
                ));
            }
        }
        Ok(theme)
    }

    /// Look up a reviewed token, without assigning any semantic state to it.
    #[must_use]
    pub fn token(&self, role: &str) -> Option<&str> {
        self.tokens.get(role).map(String::as_str)
    }
}

/// Load the compile-time bundled theme without depending on a running Core.
///
/// # Errors
/// Fails if the compiled presentation asset violates the reviewed contract.
pub fn bundled_theme() -> Result<UiTheme, ContractError> {
    UiTheme::parse(BUNDLED_THEME.as_bytes())
}

#[cfg(test)]
mod tests {
    use super::{bundled_theme, UiTheme, BUNDLED_THEME, UI_THEME_SCHEMA};
    use serde_json::Value;

    #[test]
    fn exact_owner_palette_survives_bundling() {
        let theme = bundled_theme().expect("checked in UI palette must validate");
        assert_eq!(theme.schema, UI_THEME_SCHEMA);
        assert_eq!(theme.tokens.len(), 22);
        assert_eq!(theme.token("primary"), Some("#9400D3"));
        assert_eq!(theme.token("accent"), Some("#00C2FF"));
        assert_eq!(theme.token("tertiary"), Some("#39FF14"));
        assert_eq!(theme.token("background"), Some("#000000"));
        assert_eq!(theme.token("surface_card"), Some("#0B1020"));
        assert_eq!(theme.token("danger"), Some("#9F0202"));
        assert_eq!(theme.token("text_main"), Some("#E5E7EB"));
        assert_eq!(theme.token("hover"), Some("#AA1DFF"));
    }

    #[test]
    fn reject_unknown_tokens_and_schema() {
        let mut value: Value = serde_json::from_str(BUNDLED_THEME).expect("valid fixture JSON");
        value["tokens"]["surprise"] = Value::String("#123456".to_owned());
        assert!(UiTheme::parse(value.to_string().as_bytes()).is_err());
        value["tokens"]
            .as_object_mut()
            .expect("fixture map")
            .remove("surprise");
        value["schema"] = Value::String("aegis.ui.theme.v2".to_owned());
        assert!(UiTheme::parse(value.to_string().as_bytes()).is_err());
    }

    #[test]
    fn reject_missing_tokens_malformed_hex_and_duplicate_keys() {
        let missing = BUNDLED_THEME.replace("\"#9400D3\"", "\"#notHEX\"");
        assert!(UiTheme::parse(missing.as_bytes()).is_err());
        let duplicate = r#"{"schema":"aegis.ui.theme.v1","schema":"aegis.ui.theme.v1"}"#;
        assert!(UiTheme::parse(duplicate.as_bytes()).is_err());
        let mut value: Value = serde_json::from_str(BUNDLED_THEME).expect("valid fixture");
        value["tokens"]
            .as_object_mut()
            .expect("fixture map")
            .remove("primary");
        assert!(UiTheme::parse(value.to_string().as_bytes()).is_err());
    }
}
