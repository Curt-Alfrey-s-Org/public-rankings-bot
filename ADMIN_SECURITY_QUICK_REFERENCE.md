# Admin Security Dashboard - Quick Reference

## Accessing the Dashboard

1. Log in as **admin** or **super_admin**
2. Navigate to **Admin** → **Security Dashboard**
3. Choose your tool from three tabs

---

## Tab 1: Bulk User Import 📥

**Use this to:** Create accounts for all tournament players at once

### Steps:
1. Get player list from Fargo/WPA/WPBA
2. Format as CSV: `name, fargo_rating, state, fargo_id`
3. Paste into **Bulk User Import** box
4. Click **Create Users**
5. Review created accounts in table
6. Click **Download CSV**
7. Distribute CSV to WPA/WPBA presidents

### Output Format:
```
john_smith,X9#kL2@mP5!,John Smith,800,CA,12345
jane_doe,Y8@kM3#oQ6!,Jane Doe,750,NY,12346
```

### Notes:
- Usernames auto-generated from last name + first initial
- Passwords auto-generated (12 chars, secure format)
- Players must set email + new password on first login

---

## Tab 2: Login Monitoring 📊

**Use this to:** Track failed login attempts and detect suspicious activity

### View Options:
- **Time Range:** 1 hour to 7 days (default: 24 hours)
- **Failed Only:** Toggle to see only failed attempts
- **Auto-Refresh:** Updates every 30 seconds

### Columns:
| Column | What It Means |
|--------|--------------|
| Username | Who tried to log in |
| IP Address | Where they logged in from |
| Status | Success ✓ or Failed ✗ |
| Reason | Why failed (invalid_password, account_locked, etc.) |
| Time | When it happened |

### Examples:
- **Multiple failures from same IP** → Possible brute-force attack
- **Failures followed by success** → User forgot password, then got it right
- **Account locked status** → Too many failed attempts (auto-locked 30 min)

---

## Tab 3: User Security 🔐

**Use this to:** Check/unlock individual user accounts

### Steps:
1. Type username in search box
2. Click **Load**
3. View security info:
   - Failed attempt count
   - Lock status & countdown timer
   - Recent IP addresses
   - Attempt history (last 24h)

### Actions:
- **Unlock Button** (if account locked) → Manually remove 30-min lock
- **Load Status** → Refresh data from server

### Example Scenarios:

**Locked Account:**
```
Username: john_smith
Failed Attempts: 5
Status: LOCKED
Time Remaining: 18 minutes
Recent IPs: 198.51.100.103
```
→ Click **Unlock** if legitimate user needs immediate access

**Suspicious Activity:**
```
Failed Attempts: 2 (from IP 91.234.16.100)
Recent IPs: 83.101.45.200, 91.234.16.100, 203.45.67.89
```
→ Multiple different IPs = user moving around (OK)  
→ Same IP with failures = possible attack (monitor)

---

## Workflow Examples

### Scenario 1: Tournament Registration
**Time:** 30 seconds per player

```
1. Get list of 20 players from WPA
2. Format: John Smith,800,CA,12345
3. Paste 20 players into Bulk Import
4. Click Create Users
5. Download CSV → Send to WPA president
```

### Scenario 2: Unlock Locked Account
**Time:** 5 seconds

```
1. Player calls: "I can't log in!"
2. Go to User Security tab
3. Search: username
4. See: LOCKED, 25 minutes remaining
5. Click Unlock
6. Tell player: "Try again now"
```

### Scenario 3: Investigate Failed Logins
**Time:** 2 minutes

```
1. Go to Login Monitoring
2. Filter: Last 24 hours, Failed only
3. See: 47 failed attempts from IP 202.14.89.100
4. Search that user in User Security
5. See: Legitimate player from different city today
6. Decision: Help player reset password
```

---

## Status Codes & Meanings

| Code | Situation | Action |
|------|-----------|--------|
| ✓ Success | Normal login | None needed |
| ✗ invalid_password | Wrong password | User will retry |
| ✗ account_locked | Too many failures | Auto-unlocks in 30 min (or unlock manually) |
| ✗ invalid_user | User doesn't exist | Check spelling |

---

## Tips & Best Practices

✅ **DO:**
- Review failed attempts weekly (check for attacks)
- Unlock accounts immediately for legitimate users
- Keep CSV exports secure when distributing
- Note IP addresses of known locations (work, home, phone)

❌ **DON'T:**
- Share passwords once distributed (use "Forgot Password" instead)
- Leave failed logins unreviewed (could be brute-force)
- Bulk create accounts without verifying Fargo data
- Forget to have players set email on first login

---

## Common Questions

**Q: How do I reset a player's password?**  
A: Tell them to click "Forgot Password" at login. They reset it themselves using their email.

**Q: Can I change a player's username?**  
A: No. Username is permanent. Advise players to remember it or write it down.

**Q: What's the email field for?**  
A: Password resets and account recovery. Players set it on first login.

**Q: How long are accounts locked?**  
A: 30 minutes after 5 failed attempts. You can unlock immediately if needed.

**Q: Can I see what a player's password is?**  
A: No. It's encrypted. If they forget, they use "Forgot Password" (sent via email).

**Q: What if someone attacks from multiple IPs?**  
A: Account locks after 5 fails from any IP. Monitor Login Monitoring tab for patterns.

---

## Quick Keyboard Shortcut
- Copy CSV output directly → Paste to email/message
- Search box auto-focuses when you click User Security tab
- Refresh button updates all stats in Login Monitoring

---

## Support

For issues with:
- **Bulk create errors** → Check CSV format (name, rating, state, id)
- **Unlock not working** → Verify you're super_admin (not just admin)
- **Login attempts not showing** → They show in real-time, auto-refresh running
- **Missing player** → Search exact username (case-insensitive)

---

Version: 1.0 (Jan 2024)  
Last Updated: Admin Security Dashboard Go-Live
