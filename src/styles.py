import streamlit as st

def apply_custom_css():
    """
    Applies global custom CSS for a stylish, white-based design.
    """
    st.markdown("""
        <style>
        /* Import Google Fonts */
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@300;400;500;700&display=swap');
        @import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200');

        /* Global Font Settings */
        html, body, [class*="css"]  {
            font-family: 'Noto Sans JP', sans-serif;
            color: #333333;
            background-color: #FFFFFF;
        }
        
        /* Material Icons Class */
        .material-symbols-rounded {
            font-family: 'Material Symbols Rounded';
            font-weight: normal;
            font-style: normal;
            font-size: 24px;  /* Default size */
            display: inline-block;
            line-height: 1;
            text-transform: none;
            letter-spacing: normal;
            word-wrap: normal;
            white-space: nowrap;
            direction: ltr;
            vertical-align: middle;
            /* Support for all WebKit browsers. */
            -webkit-font-smoothing: antialiased;
            /* Support for Safari and Chrome. */
            text-rendering: optimizeLegibility;
            /* Support for Firefox. */
            -moz-osx-font-smoothing: grayscale;
            /* Support for IE. */
            font-feature-settings: 'liga';
        }

        /* --- Headings --- */
        h1, h2, h3 {
            font-weight: 700;
            color: #1E3A8A; /* Deep Blue */
            margin-bottom: 0.5em;
        }
        h1 {
            border-bottom: 2px solid #E5E7EB;
            padding-bottom: 0.3em;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        /* --- Metrics Cards --- */
        div[data-testid="stMetric"] {
            background-color: #FFFFFF;
            border: 1px solid #F3F4F6;
            border-radius: 12px;
            padding: 10px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
            text-align: center;
            min-height: 80px; /* Reduced from 120px */
            display: flex;
            flex-direction: column;
            justify-content: center; /* Vertical center */
            align-items: center;     /* Horizontal center */
            margin-top: 20px;        /* Move down from header */
        }
        
        div[data-testid="stMetric"] label {
            width: 100%;
            justify-content: center;
            color: #6B7280; /* Muted text */
            font-size: 0.9em;
            margin-bottom: 5px; /* Adjust spacing */
        }
        
        div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
            width: 100%;
            justify-content: center;
            font-size: 2em;
            font-weight: 700;
            color: #1E3A8A;
            padding-bottom: 0px !important; /* Remove excessive padding if any */
        }

        /* --- Containers / Cards --- */
        /* Target generic containers or expanders to look like cards */
        div[data-testid="stExpander"], div[data-testid="stForm"] {
            background-color: #FFFFFF;
            border-radius: 12px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
            border: 1px solid #F3F4F6;
            margin-bottom: 1em;
            padding: 1em;
        }

        /* --- Buttons --- */
        div.stButton > button {
            border-radius: 8px;
            border: 1px solid #E5E7EB;
            background-color: #F9FAFB;
            color: #374151;
            font-weight: 500;
            transition: all 0.2s ease;
        }
        div.stButton > button:hover {
            border-color: #1E3A8A;
            color: #1E3A8A;
            background-color: #EFF6FF;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }

        /* Primary Button (Action) */
        div.stButton > button[kind="primary"] {
            background: linear-gradient(135deg, #1E3A8A 0%, #3B82F6 100%);
            color: #FFFFFF;
            border: none;
            box-shadow: 0 4px 6px rgba(59, 130, 246, 0.3);
        }
        div.stButton > button[kind="primary"]:hover {
            box-shadow: 0 6px 8px rgba(59, 130, 246, 0.4);
            transform: translateY(-1px);
        }

        /* --- Inputs --- */
        input[type="text"], input[type="number"], textarea, select {
            border-radius: 6px;
            border: 1px solid #D1D5DB;
        }
        
        /* --- Sidebar --- */
        section[data-testid="stSidebar"] {
            background-color: #F8FAFC;
            border-right: 1px solid #E5E7EB;
        }

        /* Custom utility classes */
        .card {
            background-color: white;
            padding: 1.5rem;
            border-radius: 0.5rem;
            box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06);
        }
        
        .header-icon {
            font-size: 32px;
            color: #1E3A8A;
            vertical-align: bottom;
            margin-right: 8px;
        }
        
        /* === Mobile Responsive Styles === */
        @media screen and (max-width: 768px) {
            /* Slightly smaller headings on mobile (adjusted from too small) */
            h1 {
                font-size: 1.5rem !important;
            }
            h2 {
                font-size: 1.3rem !important;
            }
            h3 {
                font-size: 1.1rem !important;
            }
            
            /* Smaller header icon on mobile */
            .header-icon {
                font-size: 26px !important;
            }
            
            /* Title text */
            [data-testid="stAppViewContainer"] h1 {
                font-size: 1.4rem !important;
                line-height: 1.3;
            }
            
            /* Compact metric cards for mobile */
            div[data-testid="stMetric"] {
                min-height: 50px !important;
                padding: 6px 8px !important;
                margin-top: 5px !important;
            }
            div[data-testid="stMetric"] label {
                font-size: 0.7rem !important;
                margin-bottom: 2px !important;
            }
            div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
                font-size: 1.2em !important;
            }
            
            /* Button text */
            div.stButton > button {
                font-size: 0.9rem !important;
                padding: 0.5rem 0.8rem !important;
            }
            
            /* Compact expander headers */
            div[data-testid="stExpander"] summary {
                font-size: 0.95rem !important;
            }
            
            /* Reduce column gap for metric columns */
            [data-testid="stHorizontalBlock"] {
                gap: 0.3rem !important;
            }
        }
        
        /* Extra small screens (phones in portrait) */
        @media screen and (max-width: 480px) {
            h1 {
                font-size: 1.3rem !important;
            }
            h2 {
                font-size: 1.1rem !important;
            }
            .header-icon {
                font-size: 22px !important;
            }
            
            /* Even more compact metrics on very small screens */
            div[data-testid="stMetric"] {
                min-height: 45px !important;
                padding: 4px 6px !important;
            }
            div[data-testid="stMetric"] label {
                font-size: 0.65rem !important;
            }
            div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
                font-size: 1.0em !important;
            }
        }
        </style>
    """, unsafe_allow_html=True)
    
    # Scroll to top and close sidebar on mobile using components.html with delay for page render
    import streamlit.components.v1 as components
    components.html(
        """
        <script>
            // Delayed execution to ensure page is fully rendered
            setTimeout(function() {
                // Scroll to top
                try {
                    window.parent.scrollTo(0, 0);
                    var mainSection = window.parent.document.querySelector('section.main');
                    if (mainSection) mainSection.scrollTo(0, 0);
                    var appViewContainer = window.parent.document.querySelector('[data-testid="stAppViewContainer"]');
                    if (appViewContainer) appViewContainer.scrollTo(0, 0);
                } catch (e) { console.error(e); }

                // モバイルでサイドバーを確実に閉じるためのポーリング処理
                var checkCount = 0;
                var maxChecks = 50; // 300ms * 50 = 15秒間監視
                
                var sidebarChecker = setInterval(function() {
                    checkCount++;
                    if (checkCount > maxChecks) {
                        clearInterval(sidebarChecker);
                        return;
                    }

                    // モバイル判定 (幅998px以下に緩和 - タブレットや大型スマホ対応)
                    var width = window.parent.innerWidth || window.innerWidth;
                    if (width <= 998) {
                        var doc = window.parent.document;
                        
                        // サイドバーの状態を確認
                        var sidebar = doc.querySelector('section[data-testid="stSidebar"]');
                        var isExpanded = sidebar && (sidebar.getAttribute('aria-expanded') === 'true' || sidebar.style.width === '336px');
                        
                        if (isExpanded) {
                            // 閉じボタンを探してクリック（セレクタをさらに追加）
                            var closeButtons = [
                                'button[aria-label="Close sidebar"]',
                                'section[data-testid="stSidebar"] button[kind="header"]',
                                '[data-testid="stSidebarCollapseButton"]',
                                '[data-testid="collapsedControl"] button',
                                'button[data-testid="baseButton-header"]' // 新しいStreamlitバージョンの可能性
                            ];
                            
                            var clicked = false;
                            for (var i = 0; i < closeButtons.length; i++) {
                                var btn = doc.querySelector(closeButtons[i]);
                                if (btn) {
                                    btn.click();
                                    clicked = true;
                                    break;
                                }
                            }
                            
                            // ボタンが見つからない場合のフォールバック：データ属性を強制書き換え
                            if (!clicked && sidebar) {
                                sidebar.setAttribute('aria-expanded', 'false');
                                // 無理やり閉じた状態にするのは描画崩れの恐れがあるため、
                                // ボタンクリックが最優先だが、やむを得ない場合はスタイル調整
                                // sidebar.style.display = 'none'; // これは危険なのでやらない
                            }
                        }
                    } else {
                        // PCサイズなら何もしないで終了
                        clearInterval(sidebarChecker);
                    }
                }, 300);
            }, 100);
        </script>
        """,
        height=0,
    )
