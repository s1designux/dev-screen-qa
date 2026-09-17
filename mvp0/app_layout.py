"""Native-app comparison layout; web retains its existing horizontal-screen layout."""

def is_app(platform):
    return (platform or '').lower() in ('android', 'ios')


CSS = '''
.app-view .app-workspace{display:grid;grid-template-columns:minmax(0,1fr) 420px;gap:var(--spacing-20);flex:1;min-height:0;padding-bottom:var(--spacing-16)}
.app-view .app-workspace>.cols,.app-view .app-workspace>.compare{height:100%;min-height:0;margin:0;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:var(--spacing-14)}
.app-view .app-sidebar{display:flex;flex-direction:column;min-width:0;min-height:0;overflow:hidden}
.app-view .app-sidebar .grid{grid-template-columns:minmax(0,1fr)}
.app-view .app-sidebar .cards,.app-view .app-sidebar .review-scroll{flex:1;min-height:0;overflow-y:auto}
.app-view .app-sidebar .review-actions{display:flex;flex-direction:column;align-items:stretch;gap:var(--spacing-10);margin-bottom:var(--spacing-20)}
.app-view .app-sidebar .review-actions button{width:100%}
.app-view .app-sidebar .review-actions p{flex:none;margin:0 0 var(--spacing-4)}
.app-view .app-sidebar .review-tabs,.app-view .app-sidebar .tabbar{flex-wrap:wrap;row-gap:var(--spacing-10)}
/* 앱 검수는 옆칸이 좁다 — 성질 칩을 탭 아랫줄로 내린다(river 2026-09-17) */
.app-view .app-sidebar .fbar{flex:1 1 100%;margin-left:0;display:flex;justify-content:flex-start;row-gap:var(--spacing-8);padding-block:var(--spacing-6)}
.app-view .app-sidebar .passform{flex-wrap:wrap}.app-view .app-sidebar .passform input{min-width:0}
.app-view .app-sidebar .issue{padding:var(--spacing-16);overflow-wrap:anywhere}
@media(max-width:1000px){
  body.app-view{height:auto;min-height:100%;overflow:auto}
  .app-view main.detail,.app-view .wrap{flex:none;min-height:0}
  .app-view .app-workspace{display:flex;flex-direction:column;flex:none;min-height:0}
  .app-view .app-workspace>.cols,.app-view .app-workspace>.compare{height:80vh;min-height:380px;flex:none}
  .app-view .app-sidebar{min-height:220px;overflow:visible}
  .app-view .app-sidebar .cards,.app-view .app-sidebar .review-scroll{flex:none;max-height:none;overflow:visible}
  .app-view .app-sidebar .review-actions{flex-direction:row;align-items:center;flex-wrap:wrap}
  .app-view .app-sidebar .review-actions p{flex-basis:100%}
}
'''
