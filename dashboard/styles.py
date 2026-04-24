"""Dark theme CSS and HTML template for the Dash application."""

INDEX_STRING = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
            /* ==============================================
               Dark Theme CSS - PyQt6 Design System Alignment
               ============================================== */

            /* Base Styles */
            * {
                box-sizing: border-box;
            }

            body {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                background-color: #1f1f1f;
                color: #888888;
                margin: 0;
                font-size: 13px;
                line-height: 1.5;
            }

            .main-container {
                margin: 0;
                padding: 16px 20px;
                background-color: #1f1f1f;
                min-height: 100vh;
            }

            /* Typography */
            h1, h2, h3, h4, h5, h6 {
                color: #888888;
                margin: 0;
                font-weight: 600;
            }

            h1 {
                font-size: 20px;
                border-bottom: 2px solid #3b82f6;
                padding-bottom: 12px;
                margin-bottom: 16px;
            }

            h3 {
                font-size: 16px;
                color: #3b82f6;
            }

            p {
                color: #888888;
                margin: 4px 0;
            }

            /* Tab Styling */
            .tab-parent {
                margin-bottom: 16px;
            }

            .tab {
                background-color: #353535 !important;
                color: #a0a0a0 !important;
                border: none !important;
                border-bottom: 2px solid transparent !important;
                font-weight: 600 !important;
                font-size: 14px !important;
                padding: 10px 20px !important;
                border-top-left-radius: 6px !important;
                border-top-right-radius: 6px !important;
                margin-right: 4px !important;
                transition: all 0.2s ease !important;
            }

            .tab:hover {
                background-color: #404040 !important;
                color: #888888 !important;
            }

            .tab--selected {
                background-color: #2a2a2a !important;
                color: #3b82f6 !important;
                border-bottom: 2px solid #3b82f6 !important;
            }

            .tab-content {
                background-color: #2a2a2a;
                border: 1px solid #3d3d3d;
                border-radius: 0 6px 6px 6px;
                padding: 16px;
            }

            /* Control Panel */
            .control-panel {
                background-color: #2a2a2a;
                border: 1px solid #3d3d3d;
                padding: 16px 20px;
                border-radius: 8px;
                margin-bottom: 16px;
            }

            .control-panel-row {
                display: flex;
                flex-wrap: wrap;
                gap: 24px;
                align-items: flex-start;
            }

            .control-group {
                flex: 1;
                min-width: 200px;
            }

            .control-group-wide {
                flex: 2;
                min-width: 300px;
            }

            .section-label, .control-label {
                font-weight: 600;
                font-size: 12px;
                color: #a0a0a0;
                margin-bottom: 8px;
                display: block;
                text-transform: uppercase;
                letter-spacing: 0.3px;
            }

            /* Graph Grid - Single column layout, all cards full width */
            .graphs-grid {
                display: flex;
                flex-direction: column;
                gap: 20px;
                margin-top: 16px;
            }

            /* Graph Cards */
            .graph-card {
                background-color: #2a2a2a;
                border: 1px solid #3d3d3d;
                border-radius: 8px;
                padding: 16px 20px;
                box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
                display: flex;
                flex-direction: column;
            }

            /* All cards take full width in flex layout */
            .graph-card {
                width: 100%;
            }

            .card-header {
                margin-bottom: 12px;
                padding-bottom: 10px;
                border-bottom: 1px solid #3d3d3d;
            }

            .card-title {
                font-size: 16px;
                font-weight: 600;
                color: #888888;
                margin: 0 0 4px 0;
            }

            .card-subtitle {
                font-size: 12px;
                color: #a0a0a0;
                margin: 0;
                font-weight: 400;
            }

            /* Correlation line toggle checkbox */
            .corr-line-toggle {
                display: flex;
                align-items: center;
                flex-shrink: 0;
            }
            .corr-line-toggle label {
                display: flex !important;
                align-items: center;
                font-size: 12px;
                color: #a0a0a0;
                cursor: pointer;
                white-space: nowrap;
            }
            .corr-line-toggle input[type="checkbox"] {
                accent-color: #3b82f6;
                margin-right: 2px;
                cursor: pointer;
            }

            /* Control Toolbar */
            .control-toolbar {
                display: flex;
                flex-wrap: wrap;
                gap: 16px 24px;
                align-items: flex-end;
                margin-bottom: 12px;
                padding: 12px 16px;
                background-color: #353535;
                border: 1px solid #4a4a4a;
                border-radius: 6px;
            }

            .toolbar-group {
                display: flex;
                align-items: flex-end;
                gap: 12px;
            }

            .inline-control {
                display: flex;
                flex-direction: column;
            }

            .inline-label {
                font-size: 11px;
                font-weight: 600;
                color: #a0a0a0;
                margin-bottom: 4px;
                text-transform: uppercase;
                letter-spacing: 0.3px;
            }

            /* Input Fields */
            input[type="number"],
            input[type="text"] {
                background-color: #2a2a2a;
                border: 1px solid #4a4a4a;
                border-radius: 4px;
                color: #888888;
                padding: 6px 10px;
                font-size: 12px;
                width: 60px;
                transition: border-color 0.2s ease;
            }

            input[type="number"]:focus,
            input[type="text"]:focus {
                border-color: #3b82f6;
                outline: none;
                box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2);
            }

            input[type="number"]::placeholder,
            input[type="text"]::placeholder {
                color: #a0a0a0;
            }

            /* Range separator */
            .range-separator {
                color: #707070;
                margin: 0 6px;
                font-weight: 500;
            }

            /* Dropdown Overrides (Dash/React-Select) - Comprehensive Dark Theme */
            /* Main dropdown container */
            .Select-control,
            .dash-dropdown .Select-control,
            .VirtualizedSelectFocusedOption,
            div[class*="dropdown"] .Select-control {
                background-color: #2a2a2a !important;
                border-color: #4a4a4a !important;
                border-radius: 6px !important;
                min-height: 36px !important;
            }

            .Select-control:hover,
            .dash-dropdown .Select-control:hover {
                border-color: #5a5a5a !important;
            }

            .is-focused .Select-control,
            .dash-dropdown.is-focused .Select-control {
                border-color: #3b82f6 !important;
                box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2) !important;
            }

            /* ALL dropdown text - darker grey for better visibility */
            .Select-value,
            .Select-value *,
            .Select-value-label,
            .Select-input,
            .Select-input input,
            .dash-dropdown .Select-value,
            .dash-dropdown .Select-value *,
            .dash-dropdown .Select-value-label,
            .dash-dropdown .Select-input,
            .dash-dropdown .Select-input input,
            .Select--single .Select-value,
            .Select--single .Select-value-label,
            .Select--multi .Select-value,
            .Select--multi .Select-value-label,
            .Select-control:hover .Select-value,
            .Select-control:hover .Select-value *,
            .Select-control:hover .Select-value-label,
            .dash-dropdown:hover .Select-value,
            .dash-dropdown:hover .Select-value *,
            .dash-dropdown:hover .Select-value-label {
                color: #888888 !important;
                opacity: 1 !important;
            }

            /* Placeholder - slightly dimmer */
            .Select-placeholder,
            .dash-dropdown .Select-placeholder {
                color: #707070 !important;
                opacity: 1 !important;
            }

            /* Dropdown menu */
            .Select-menu-outer,
            .dash-dropdown .Select-menu-outer {
                background-color: #2a2a2a !important;
                border-color: #4a4a4a !important;
                border-radius: 6px !important;
                margin-top: 4px !important;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3) !important;
                z-index: 9999 !important;
            }

            .Select-menu,
            .dash-dropdown .Select-menu,
            .VirtualizedSelectOption {
                background-color: #2a2a2a !important;
            }

            .Select-option,
            .dash-dropdown .Select-option,
            .VirtualizedSelectOption {
                background-color: #2a2a2a !important;
                color: #888888 !important;
                padding: 10px 12px !important;
            }

            .Select-option:hover,
            .Select-option.is-focused,
            .dash-dropdown .Select-option:hover,
            .dash-dropdown .Select-option.is-focused,
            .VirtualizedSelectFocusedOption {
                background-color: #3d5a80 !important;
                color: #7cb3f0 !important;
            }

            .Select-option.is-selected,
            .dash-dropdown .Select-option.is-selected,
            .VirtualizedSelectSelectedOption {
                background-color: #3b82f6 !important;
                color: white !important;
            }

            /* Dropdown arrows and icons */
            .Select-arrow-zone,
            .dash-dropdown .Select-arrow-zone {
                color: #a0a0a0 !important;
            }

            .Select-clear-zone,
            .dash-dropdown .Select-clear-zone {
                color: #a0a0a0 !important;
            }

            .Select-arrow,
            .dash-dropdown .Select-arrow {
                border-color: #a0a0a0 transparent transparent !important;
            }

            .is-open .Select-arrow,
            .dash-dropdown.is-open .Select-arrow {
                border-color: transparent transparent #a0a0a0 !important;
            }

            /* Multi-select tags - always visible */
            .Select--multi .Select-value,
            .dash-dropdown .Select--multi .Select-value {
                background-color: #3b82f6 !important;
                border-color: #2563eb !important;
                color: white !important;
                border-radius: 4px !important;
                margin: 2px !important;
                opacity: 1 !important;
            }

            .Select--multi .Select-value-label,
            .dash-dropdown .Select--multi .Select-value-label {
                color: white !important;
                opacity: 1 !important;
            }

            .Select--multi .Select-value-icon,
            .dash-dropdown .Select--multi .Select-value-icon {
                border-color: rgba(255,255,255,0.3) !important;
                color: white !important;
                opacity: 1 !important;
            }

            /* Single value display fix - darker grey */
            .Select--single .Select-value,
            .dash-dropdown .Select--single .Select-value {
                color: #888888 !important;
                opacity: 1 !important;
            }

            /* Input field inside dropdown - darker grey */
            .Select-input,
            .dash-dropdown .Select-input {
                color: #888888 !important;
            }

            .Select-input input,
            .dash-dropdown .Select-input input {
                color: #888888 !important;
                background: transparent !important;
            }

            /* Catch-all for any text inside dropdown - always visible */
            .dash-dropdown span,
            .dash-dropdown div,
            .Select span,
            .Select div {
                color: inherit !important;
                opacity: 1 !important;
            }

            /* No options message */
            .Select-noresults,
            .dash-dropdown .Select-noresults {
                color: #707070 !important;
                padding: 10px 12px !important;
            }

            /* Checklist Styling */
            .checklist-container label {
                display: inline-flex !important;
                align-items: center;
                margin-right: 24px;
                font-size: 13px;
                color: #888888;
                cursor: pointer;
                padding: 6px 0;
            }

            .checklist-container input[type="checkbox"] {
                appearance: none;
                -webkit-appearance: none;
                width: 18px;
                height: 18px;
                border: 2px solid #4a4a4a;
                border-radius: 4px;
                background-color: #2a2a2a;
                margin-right: 8px;
                cursor: pointer;
                position: relative;
                transition: all 0.2s ease;
            }

            .checklist-container input[type="checkbox"]:hover {
                border-color: #3b82f6;
            }

            .checklist-container input[type="checkbox"]:checked {
                background-color: #3b82f6;
                border-color: #3b82f6;
            }

            .checklist-container input[type="checkbox"]:checked::after {
                content: '';
                position: absolute;
                left: 5px;
                top: 2px;
                width: 4px;
                height: 8px;
                border: solid white;
                border-width: 0 2px 2px 0;
                transform: rotate(45deg);
            }

            /* Slider Styling */
            .rc-slider {
                margin: 8px 0 !important;
            }

            .rc-slider-track {
                background-color: #3b82f6 !important;
                height: 4px !important;
            }

            .rc-slider-rail {
                background-color: #4a4a4a !important;
                height: 4px !important;
            }

            .rc-slider-handle {
                border-color: #3b82f6 !important;
                background-color: #3b82f6 !important;
                width: 14px !important;
                height: 14px !important;
                margin-top: -5px !important;
            }

            .rc-slider-handle:hover,
            .rc-slider-handle:active,
            .rc-slider-handle:focus {
                border-color: #2563eb !important;
                box-shadow: 0 0 0 4px rgba(59, 130, 246, 0.2) !important;
            }

            .rc-slider-mark-text {
                color: #a0a0a0 !important;
                font-size: 11px !important;
            }

            .rc-slider-dot {
                background-color: #4a4a4a !important;
                border-color: #4a4a4a !important;
            }

            .rc-slider-dot-active {
                background-color: #3b82f6 !important;
                border-color: #3b82f6 !important;
            }

            /* Stats Box (Single File) - Dark Theme */
            .stats-box {
                background-color: #2a2a2a;
                border: 1px solid #3d3d3d;
                border-left: 3px solid #3b82f6;
                border-radius: 6px;
                padding: 12px 16px;
                margin-top: 12px;
            }

            .stats-box h4 {
                font-size: 13px;
                font-weight: 600;
                color: #888888;
                margin: 0 0 8px 0;
            }

            .stats-box p {
                font-size: 12px;
                color: #a0a0a0;
                margin: 4px 0;
            }

            /* Empty State */
            .empty-state {
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                min-height: 200px;
                background: #2a2a2a;
                border: 2px dashed #4a4a4a;
                border-radius: 8px;
                color: #707070;
                padding: 24px;
            }

            .empty-state-icon {
                font-size: 36px;
                margin-bottom: 12px;
                opacity: 0.6;
            }

            .empty-state-text {
                font-size: 14px;
                text-align: center;
            }

            /* PCA Variance Info Badge */
            .variance-badge {
                display: inline-flex;
                align-items: center;
                background-color: #353535;
                border: 1px solid #4a4a4a;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 12px;
                color: #a0a0a0;
            }

            .variance-badge strong {
                color: #3b82f6;
                margin-left: 4px;
            }


            /* Stats Items (Single File) */
            .stat-item {
                display: flex;
                justify-content: space-between;
                padding: 6px 0;
                border-bottom: 1px solid #3d3d3d;
            }

            .stat-item:last-child {
                border-bottom: none;
            }

            .stat-label {
                color: #a0a0a0;
                font-size: 12px;
            }

            .stat-value {
                color: #888888;
                font-size: 12px;
                font-weight: 500;
            }

            /* Range Separator */
            .range-separator {
                color: #707070;
                margin: 0 6px;
                font-weight: 500;
            }

            /* Scrollbar Styling */
            ::-webkit-scrollbar {
                width: 10px;
                height: 10px;
            }

            ::-webkit-scrollbar-track {
                background: #1f1f1f;
                border-radius: 5px;
            }

            ::-webkit-scrollbar-thumb {
                background: #4a4a4a;
                border-radius: 5px;
            }

            ::-webkit-scrollbar-thumb:hover {
                background: #5a5a5a;
            }

            /* Responsive adjustments */
            @media (max-width: 1024px) {
                .control-panel-row {
                    flex-direction: column;
                }

                .control-group,
                .control-group-wide {
                    width: 100%;
                }

                .control-toolbar {
                    flex-wrap: wrap;
                }

                .toolbar-group {
                    width: 100%;
                    margin-bottom: 8px;
                }
            }

            /* HIGH SPECIFICITY: Target specific dropdown IDs for text color */
            #multi-file-selector .Select-value-label,
            #multi-file-selector .Select-value,
            #multi-file-selector span,
            #file-selector .Select-value-label,
            #file-selector .Select-value,
            #file-selector span,
            #ts-metric .Select-value-label,
            #ts-metric .Select-value,
            #ts-metric span,
            #explorer-x .Select-value-label,
            #explorer-x .Select-value,
            #explorer-y .Select-value-label,
            #explorer-y .Select-value,
            #pca-color .Select-value-label,
            #pca-color .Select-value,
            #sf-x-feature .Select-value-label,
            #sf-x-feature .Select-value,
            #sf-y-feature .Select-value-label,
            #sf-y-feature .Select-value,
            #corr-file-selector .Select-value-label,
            #corr-file-selector .Select-value,
            #corr-file-selector span,
            #corr-psi-filter .Select-value-label,
            #corr-psi-filter .Select-value,
            #corr-psi-filter span,
            #pred-wafer .Select-value-label,
            #pred-wafer .Select-value,
            #pred-pad .Select-value-label,
            #pred-pad .Select-value,
            #pred-slurry .Select-value-label,
            #pred-slurry .Select-value,
            #pred-conditioner .Select-value-label,
            #pred-conditioner .Select-value {
                color: #888888 !important;
                opacity: 1 !important;
                font-weight: 500 !important;
                -webkit-font-smoothing: antialiased !important;
            }

            /* Correlation Explorer 2x3 Grid */
            .correlation-grid {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 16px;
                margin-top: 16px;
            }

            .correlation-grid .graph-card {
                min-height: 350px;
            }

            /* Hide Plotly's built-in snapshot notification overlay */
            .plotly-notifier {
                display: none !important;
            }

            /* PCA selection details row (z-scores + categories side by side) */
            .pca-selection-row {
                display: flex;
                gap: 16px;
                align-items: stretch;
            }
            .pca-selection-row > div { min-width: 0; }

            /* Diagnostics 3-column grid (loadings, silhouette, scree) */
            .diagnostics-row {
                display: grid;
                grid-template-columns: repeat(3, minmax(0, 1fr));
                gap: 16px;
            }
            .diagnostics-row > div {
                min-width: 0;
                overflow: hidden;
            }

            @media (max-width: 1600px) {
                .diagnostics-row {
                    grid-template-columns: repeat(2, minmax(0, 1fr));
                }
            }
            @media (max-width: 1024px) {
                .diagnostics-row {
                    grid-template-columns: 1fr;
                }
                .pca-selection-row {
                    flex-direction: column;
                }
            }

            /* Prediction Tab */
            .prediction-grid {
                display: grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 16px;
                margin-top: 16px;
            }
            .prediction-grid > div {
                min-width: 0;
                overflow: hidden;
            }
            @media (max-width: 1024px) {
                .prediction-grid {
                    grid-template-columns: 1fr;
                }
            }

            .pred-result-box {
                background-color: #2a2a2a;
                border: 1px solid #3d3d3d;
                border-left: 3px solid #3b82f6;
                border-radius: 6px;
                padding: 14px 18px;
                margin-top: 12px;
            }

            .pred-btn {
                background-color: #3b82f6;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
                font-size: 13px;
                font-weight: 600;
                cursor: pointer;
                transition: background-color 0.2s ease;
                white-space: nowrap;
            }
            .pred-btn:hover {
                background-color: #2563eb;
            }

            .pred-metrics {
                display: flex;
                flex-wrap: wrap;
                gap: 8px;
            }

            /* ── AI Agent Chat ─────────────────────────────────────────── */
            /* The chat column is a fixed-height flex column. Status bar,
               suggestions, and input must stay at their natural size even
               when the capabilities panel is expanded — otherwise flex's
               default shrink distributes the deficit across every child
               and the input row ends up pushed below the visible area.
               flex-shrink: 0 on the chrome pins them; the panel body and
               the chat area are the only shrinkable items. */
            .agent-status-bar {
                display: flex;
                gap: 12px;
                align-items: center;
                padding: 8px 16px;
                background: #2a2a2a;
                border-bottom: 1px solid #404040;
                font-size: 12px;
                flex-shrink: 0;
            }
            .agent-status-badge {
                padding: 3px 10px;
                border-radius: 12px;
                background: #353535;
                color: #888888;
                font-size: 11px;
            }
            .agent-status-badge.active {
                background: #1a3a1a;
                color: #22c55e;
            }
            /* ── "How can I help?" panel ────────────────────────────── */
            .agent-help-panel {
                border-bottom: 1px solid #3d3d3d;
                background: #1f1f1f;
            }
            .agent-help-toggle {
                all: unset;
                display: flex;
                align-items: center;
                gap: 8px;
                padding: 8px 16px;
                width: 100%;
                box-sizing: border-box;
                color: #a0a0a0;
                font-size: 12px;
                cursor: pointer;
                user-select: none;
            }
            .agent-help-toggle:hover {
                color: #e0e0e0;
                background: #242424;
            }
            .agent-help-chevron::before {
                /* Literal character, not a CSS \\XXXX escape: the surrounding
                   Python string would otherwise interpret "\\25" as an octal
                   escape (U+0015) and CSS would only receive the trailing
                   "B8" as visible text. */
                content: '▸';
                display: inline-block;
                font-size: 10px;
                transition: transform 0.15s ease;
            }
            .agent-help-toggle.expanded .agent-help-chevron::before {
                transform: rotate(90deg);
            }
            .agent-help-body {
                padding: 14px 16px 10px;
                /* Grows with the viewport so more cards are visible without
                   scrolling on tall screens; capped so the chat area never
                   gets squeezed on short ones. */
                max-height: min(55vh, 480px);
                overflow-y: auto;
            }
            /* Sections are <details> — collapsed by default. The native
               ▸ marker is replaced with a ::before chevron for consistent
               styling across browsers. */
            .agent-help-section { margin-bottom: 10px; }
            .agent-help-section:last-of-type { margin-bottom: 0; }
            .agent-help-section-title {
                list-style: none;
                cursor: pointer;
                user-select: none;
                font-size: 10px;
                font-weight: 700;
                letter-spacing: 1px;
                text-transform: uppercase;
                color: #707070;
                padding: 6px 0;
                display: flex;
                align-items: center;
                gap: 8px;
                outline: none;
            }
            .agent-help-section-title::-webkit-details-marker { display: none; }
            .agent-help-section-title::before {
                content: '▸';
                font-size: 10px;
                color: #5a5a5a;
                transition: transform 0.15s ease;
            }
            .agent-help-section[open] > .agent-help-section-title::before {
                transform: rotate(90deg);
            }
            .agent-help-section-title:hover { color: #a0a0a0; }
            /* Grid rendered only when the section is open. */
            .agent-help-section:not([open]) .agent-help-grid { display: none; }
            .agent-help-grid {
                display: grid;
                /* Packs 2 columns at ~360 px chat width, 3+ when the
                   window is wide. Lower min than 190 px so narrow windows
                   don't force a single jumbo column. */
                grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
                gap: 8px;
                margin-top: 6px;
            }
            .agent-help-card {
                background: #2a2a2a;
                border: 1px solid #3d3d3d;
                border-radius: 6px;
                padding: 10px 12px;
                cursor: pointer;
                outline: none;             /* border-color is the focus ring */
                /* No transitions, no transforms, no z-index on hover/focus.
                   The card does not move, resize, or change stacking — only
                   border color changes. Eliminates perceived text motion. */
            }
            .agent-help-card:hover,
            .agent-help-card.selected {
                border-color: #3b82f6;
            }
            /* Keyboard focus ring — subtle, and independent of the
               :hover / .selected border so the pinned state is the
               only thing that actually means "this card owns the
               preview". */
            .agent-help-card:focus {
                box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.35);
            }
            /* A pinned (clicked) card gets a subtle tinted background so
               users can tell, at a glance, which card owns the preview. */
            .agent-help-card.selected {
                background: #1e3a5f;
            }
            .agent-help-card.selected .agent-help-card-title { color: #e5f0ff; }
            .agent-help-card-title {
                display: block;
                font-size: 12px;
                color: #e0e0e0;
                font-weight: 600;
            }
            /* ── Persistent preview pane ────────────────────────────────
               Replaces per-card ::after popovers. A popover was an
               absolutely-positioned descendant of .agent-help-body; since
               the body is a scroll container (overflow-y: auto), per the
               CSS Overflow Module Level 3 the popover was clipped to the
               body's padding box, which made tooltips for bottom-row cards
               invisible. The preview pane is a regular flow element that
               sticks to the top of the body via position: sticky, so it
               never moves around and never clips. */
            .agent-help-preview {
                position: sticky;
                top: -14px;                  /* cancels body's top padding */
                background: #181a1d;
                border: 1px solid #2c323a;
                border-radius: 6px;
                padding: 10px 12px;
                margin-bottom: 14px;
                /* Sized to just cover the tallest expanded state (title
                   + three-line description + 'Try asking:' line on the
                   longest tool, run_automl) so the pane's height does
                   NOT change when the user hovers, pins, or deselects a
                   card. Bigger would leave visible empty space below
                   short tools' content; smaller would allow the run_automl
                   case to push the sections below it down on hover. */
                min-height: 118px;
                font-size: 11.5px;
                line-height: 1.5;
                color: #c8c8c8;
                z-index: 2;                  /* above scrolled card content */
            }
            .agent-help-preview-default {
                color: #707070;
                font-style: italic;
            }
            .agent-help-preview-item { display: none; }
            .agent-help-preview-title {
                font-size: 12px;
                font-weight: 600;
                color: #e0e0e0;
                margin-bottom: 4px;
            }
            .agent-help-preview-desc {
                color: #c0c0c0;
            }
            .agent-help-preview-example {
                margin-top: 6px;
                color: #a0a0a0;
            }
            .agent-help-preview-label {
                color: #707070;
                font-style: italic;
            }
            /* Hide the default hint whenever a card is hovered or pinned.
               :focus is deliberately NOT included: it only drives the
               visual focus ring (border color), never the preview. This
               decouples "what does the preview show?" from browser focus
               transfer, so an imprecise click that sets :focus but not
               .selected can't leave a stale preview behind. */
            .agent-help-body:has(.agent-help-card:is(:hover, .selected))
                .agent-help-preview-default {
                display: none;
            }
            /* Two rules per tool — hover (transient) and .selected (pinned).
               Precedence: hover > .selected, enforced by a :not() guard
               on the pinned rule so only one preview-item is visible at
               a time. Generated at module load from ai.tool_ui.TOOL_UI. */
            {%agent_help_rules%}
            /* Narrow windows: tighter preview (drop the example line since
               the card's own short already conveys the gist), tighter grid. */
            @media (max-width: 900px) {
                .agent-help-grid {
                    grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
                }
                .agent-help-body {
                    max-height: min(60vh, 420px);
                }
                .agent-help-preview {
                    padding: 8px 10px;
                    /* Same no-jank contract, smaller budget: the example
                       line is hidden on narrow screens, so the tallest
                       content is title + description. */
                    min-height: 90px;
                    font-size: 11px;
                    line-height: 1.45;
                }
                .agent-help-preview-title { font-size: 11.5px; }
                .agent-help-preview-example { display: none; }
            }
            .agent-chat-area {
                flex: 1;
                overflow-y: auto;
                padding: 16px;
                display: flex;
                flex-direction: column;
                gap: 12px;
            }
            .agent-message {
                max-width: 95%;
                padding: 10px 14px;
                border-radius: 12px;
                font-size: 13px;
                line-height: 1.5;
                word-wrap: break-word;
            }
            .agent-message.assistant {
                align-self: flex-start;
                background: #353535;
                color: #e0e0e0;
                border-bottom-left-radius: 4px;
            }
            /* Markdown element styling inside assistant messages.
               dcc.Markdown injects <p>, <ul>, <li>, <code>, etc. — tighten
               their spacing so chat bubbles stay compact. */
            .agent-message.assistant p {
                margin: 0 0 6px 0;
            }
            .agent-message.assistant p:last-child {
                margin-bottom: 0;
            }
            .agent-message.assistant ul,
            .agent-message.assistant ol {
                margin: 4px 0;
                padding-left: 20px;
            }
            .agent-message.assistant li {
                margin: 2px 0;
            }
            .agent-message.assistant code {
                background: #2a2a2a;
                border: 1px solid #454545;
                border-radius: 3px;
                padding: 1px 5px;
                font-size: 11.5px;
                font-family: ui-monospace, monospace;
                color: #d0d0d0;
            }
            .agent-message.assistant strong {
                color: #f5f5f5;
            }
            .agent-message.assistant a {
                color: #60a5fa;
            }
            .agent-message.user {
                align-self: flex-end;
                background: #1e3a5f;
                color: #e0e0e0;
                border-bottom-right-radius: 4px;
            }
            .agent-message.system {
                align-self: center;
                background: transparent;
                color: #888888;
                font-style: italic;
                text-align: center;
                font-size: 12px;
            }
            .agent-tool-indicator {
                align-self: flex-start;
                font-size: 11px;
                color: #9ca3af;
                padding: 4px 10px;
                border-radius: 6px;
                background: #2a2a2a;
                border: 1px solid #3d3d3d;
                margin: 2px 0;
                font-family: ui-monospace, monospace;
                letter-spacing: 0.2px;
            }
            .agent-tool-indicator.running {
                color: #60a5fa;
                border-color: #3b82f6;
                background: #1e3a5f;
                animation: agent-tool-pulse 1.2s ease-in-out infinite;
            }
            .agent-tool-indicator.done {
                color: #6ee7b7;
                border-color: #065f46;
                background: #064e3b;
                opacity: 0.75;
            }
            .agent-tool-indicator.failed {
                color: #fca5a5;
                border-color: #7f1d1d;
                background: #450a0a;
            }
            @keyframes agent-tool-pulse {
                0%, 100% { opacity: 1.0; }
                50% { opacity: 0.55; }
            }
            .agent-thinking {
                font-size: 11px;
                color: #666666;
                padding: 4px 10px;
                border-left: 2px solid #404040;
                margin: 4px 0;
                cursor: pointer;
            }
            .agent-thinking summary {
                color: #888888;
            }
            .agent-input-area {
                display: flex;
                gap: 8px;
                padding: 12px 16px;
                background: #2a2a2a;
                border-top: 1px solid #404040;
                flex-shrink: 0;         /* must stay visible — see note above */
            }
            .agent-input-area input {
                flex: 1;
                background: #353535;
                border: 1px solid #404040;
                border-radius: 8px;
                color: #e0e0e0;
                padding: 10px 14px;
                font-size: 13px;
                outline: none;
            }
            .agent-input-area input:focus {
                border-color: #3b82f6;
            }
            .agent-send-btn {
                background: #3b82f6;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: 13px;
                font-weight: 600;
                cursor: pointer;
            }
            .agent-send-btn:hover {
                background: #2563eb;
            }
            .agent-send-btn:disabled {
                background: #404040;
                color: #666666;
                cursor: not-allowed;
            }
            .agent-suggestions {
                display: flex;
                flex-wrap: wrap;
                gap: 8px;
                justify-content: center;
                padding: 8px 16px;
                flex-shrink: 0;         /* must stay visible — see note above */
            }
            .agent-suggestion-chip {
                background: #353535;
                border: 1px solid #404040;
                border-radius: 16px;
                color: #888888;
                padding: 6px 14px;
                font-size: 12px;
                cursor: pointer;
            }
            .agent-suggestion-chip:hover {
                border-color: #3b82f6;
                color: #e0e0e0;
            }
            .agent-chart-container {
                width: 100%;
                margin: 8px 0;
                border-radius: 8px;
                overflow: hidden;
            }
            /* ── AI Agent Split (chat + canvas) ───────────────────────── */
            .agent-split {
                display: flex;
                flex-direction: row;
                gap: 0;
            }
            .agent-chat-column {
                flex: 0 0 40%;
                display: flex;
                flex-direction: column;
                border-right: 1px solid #404040;
                min-width: 0;
                min-height: 0;          /* allow flex children to shrink */
                overflow: hidden;       /* backstop: clip rather than push
                                           content past the column bottom */
            }
            .agent-canvas-column {
                flex: 1;
                display: flex;
                flex-direction: column;
                background: #1e1e1e;
                padding: 0;
                min-width: 0;
                overflow: hidden;
            }

            /* ── Tab bar ──────────────────────────────────────────────── */
            .agent-tab-bar {
                display: flex;
                flex-direction: row;
                gap: 0;
                border-bottom: 1px solid #3d3d3d;
                background: #2a2a2a;
                overflow-x: auto;
                overflow-y: hidden;
                min-height: 36px;
                flex-shrink: 0;
                scrollbar-width: thin;
                scrollbar-color: #4a4a4a transparent;
            }
            .agent-tab-bar::-webkit-scrollbar {
                height: 4px;
            }
            .agent-tab-bar::-webkit-scrollbar-thumb {
                background: #4a4a4a;
                border-radius: 2px;
            }
            .agent-tab {
                padding: 8px 16px;
                font-size: 12px;
                font-weight: 600;
                color: #a0a0a0;
                background: transparent;
                border: none;
                border-bottom: 2px solid transparent;
                cursor: pointer;
                white-space: nowrap;
                flex-shrink: 0;
                transition: color 0.15s, border-color 0.15s;
            }
            .agent-tab:hover {
                color: #e0e0e0;
                background: #353535;
            }
            .agent-tab.active {
                color: #3b82f6;
                border-bottom-color: #3b82f6;
            }
            .agent-tab-wrapper {
                display: flex;
                align-items: center;
                flex-shrink: 0;
            }
            .agent-tab-close {
                background: none;
                border: none;
                color: #707070;
                font-size: 14px;
                line-height: 1;
                padding: 2px 6px;
                margin-left: -8px;
                margin-right: 4px;
                cursor: pointer;
                border-radius: 4px;
            }
            .agent-tab-close:hover {
                color: #ef4444;
                background: #353535;
            }

            /* ── Tab content ──────────────────────────────────────────── */
            .agent-tab-content {
                flex: 1;
                min-height: 0;
                display: flex;
                flex-direction: column;
                overflow: hidden;
            }
            .agent-pred-panel {
                padding: 16px;
                display: flex;
                flex-direction: column;
                gap: 8px;
                flex: 1;
                overflow-y: auto;
            }
            .agent-pred-empty {
                flex: 1;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                text-align: center;
                color: #888888;
            }
            #agent-pred-form {
                display: flex;
                flex-direction: column;
                gap: 8px;
            }
            .agent-chart-panel {
                flex: 1;
                min-height: 0;
                min-width: 0;
                padding: 8px;
                display: flex;
                flex-direction: column;
                overflow: hidden;
            }
            /* dcc.Graph wrapper → Plotly internals: every layer must
               stretch to fill and never exceed its parent. */
            .agent-chart-panel > div,
            .agent-chart-panel .dash-graph {
                flex: 1;
                min-height: 0;
                min-width: 0;
                width: 100%;
                height: 100%;
            }
            #agent-canvas-graph {
                width: 100% !important;
                height: 100% !important;
            }
            .agent-chart-panel .js-plotly-plot {
                width: 100% !important;
                height: 100% !important;
            }
            .agent-chart-panel .plot-container {
                width: 100% !important;
                height: 100% !important;
            }
            .agent-chart-panel .svg-container {
                width: 100% !important;
                height: 100% !important;
            }
            .agent-chart-panel .main-svg {
                width: 100% !important;
                height: 100% !important;
            }
        </style>
    </head>
    <body>
        <div class="main-container">
            {%app_entry%}
        </div>
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
            <script>
                // Suppress Plotly.js animation promise rejections.
                // When Pause interrupts an ongoing animation, Plotly rejects
                // pending Plotly.animate() promises with undefined.
                window.addEventListener('unhandledrejection', function(e) {
                    if (e.reason === undefined) e.preventDefault();
                });

                // Capability-card pin/unpin.
                //
                // A clicked (or Enter/Space-ed) card gets a .selected
                // class; clicking a different card moves .selected to
                // it; clicking the already-selected card toggles it
                // off; clicks outside any card are ignored.
                //
                // We listen on `mousedown`, not `click`, because :focus
                // transfers on mousedown. If we waited for `click`, a
                // slight cursor drift between press and release (common
                // on trackpads) would suppress the click event, leaving
                // :focus set but .selected unset — and the preview
                // stuck on a card that visually looked unclicked.
                // mousedown keeps the two states in lockstep.
                (function() {
                    function selectCard(card, ev) {
                        var panel = card.closest('.agent-help-panel');
                        if (!panel) return;
                        var wasSelected = card.classList.contains('selected');
                        var prev = panel.querySelectorAll('.agent-help-card.selected');
                        for (var i = 0; i < prev.length; i++) {
                            prev[i].classList.remove('selected');
                        }
                        if (wasSelected) {
                            // Toggling off. Blur so the focus ring drops too
                            // and, if this was a mousedown, preventDefault so
                            // the browser doesn't immediately re-focus the
                            // card as the default mousedown action.
                            card.blur();
                            if (ev && ev.preventDefault) ev.preventDefault();
                        } else {
                            card.classList.add('selected');
                        }
                    }
                    document.addEventListener('mousedown', function(e) {
                        if (e.button !== 0) return;         // left-click only
                        var card = e.target.closest && e.target.closest('.agent-help-card');
                        if (card) selectCard(card, e);
                    });
                    document.addEventListener('keydown', function(e) {
                        if (e.key !== 'Enter' && e.key !== ' ') return;
                        var card = e.target.closest && e.target.closest('.agent-help-card');
                        if (!card) return;
                        e.preventDefault();                 // stop Space from scrolling
                        selectCard(card, e);
                    });
                })();
            </script>
        </footer>
    </body>
</html>
'''


# ── Inject per-tool :has() rules for the "How can I help?" preview pane ──
# Single source of truth stays in ai.tool_ui.TOOL_UI. Each rule makes the
# matching .agent-help-preview-item visible when its .agent-help-card is
# hovered. When a new capability is added to TOOL_UI, its preview rule
# appears automatically with no CSS changes required here.
def _build_agent_help_rules() -> str:
    from ai.tool_ui import TOOL_UI
    hover_tpl = (
        '.agent-help-body:has(.agent-help-card[data-name="{n}"]:hover) '
        '.agent-help-preview-item[data-name="{n}"] {{ display: block; }}'
    )
    pinned_tpl = (
        '.agent-help-body:not(:has(.agent-help-card:hover))'
        ':has(.agent-help-card[data-name="{n}"].selected) '
        '.agent-help-preview-item[data-name="{n}"] {{ display: block; }}'
    )
    rules = []
    for name in TOOL_UI:
        rules.append(hover_tpl.format(n=name))
        rules.append(pinned_tpl.format(n=name))
    return '\n            '.join(rules)


INDEX_STRING = INDEX_STRING.replace('{%agent_help_rules%}', _build_agent_help_rules())
