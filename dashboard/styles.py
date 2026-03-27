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
            </script>
        </footer>
    </body>
</html>
'''
