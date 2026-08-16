#!/bin/sh
# הפעלה בלחיצה כפולה ב-macOS / לינוקס.
# בפעם הראשונה ב-Mac: לחיצה ימנית על הקובץ ← Open ← Open (כדי לאשר הרצה).

cd "$(dirname "$0")" || exit 1

if ! command -v node >/dev/null 2>&1; then
  echo ""
  echo "  לא נמצא Node.js על המחשב."
  echo "  צריך להוריד ולהתקין מ: https://nodejs.org  (גרסת LTS), ואז לנסות שוב."
  echo ""
  printf "  לחץ Enter לסגירה..."
  read _
  exit 1
fi

# פתיחת הדפדפן אחרי שנייה, במקביל להרצת השרת
(sleep 1; (open "http://localhost:4173" || xdg-open "http://localhost:4173") >/dev/null 2>&1) &

echo ""
echo "  מפעיל את מערכת גביית שכר הדירה..."
echo "  לעצירה: Ctrl+C  |  לסגירה: פשוט לסגור את החלון הזה"
echo ""
exec node server.js
