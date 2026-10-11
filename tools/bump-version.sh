#!/bin/sh
# يضيف رقم نسخة لروابط الـcss والـjs حتى المتصفح ما يستخدم نسخة قديمة محفوظة بعد كل تحديث.
# التشغيل قبل كل رفع: sh tools/bump-version.sh
V=$(date +%Y%m%d%H%M)
for f in index.html remote.html; do
  sed -i -E "s#(href|src)=\"((css|js|vendor)/[^\"?]+)(\?v=[0-9]+)?\"#\1=\"\2?v=$V\"#g" "$f"
done
echo "version $V"
