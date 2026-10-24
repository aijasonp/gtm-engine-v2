import re
css=open('out.css').read()
css=css.replace("[data-theme='vercel'].dark",":root.dark").replace("[data-theme='vercel']",":root")
css=re.sub(r"\[data-theme\] body\s*\{[^}]*\}","",css)
css=css.replace('</style','<\\/style')
js=open('out.js').read().replace('</script','<\\/script')
head='<title>GTM Executive Snapshot Dashboard</title>\n<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700&family=Geist+Mono:wght@400;500&display=swap">\n'
html=head+'<style>'+css+'\nbody{background:var(--background);color:var(--foreground);font-family:var(--font-sans)}</style>\n<div id="root"></div>\n<script>'+js+'</script>'
open('../../gtm-preview.html','w').write(html)
print(css.count(':root.dark'))
