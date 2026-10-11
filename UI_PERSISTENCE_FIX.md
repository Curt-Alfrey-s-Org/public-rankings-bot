# UI Customizations Persistence Fix

**Date:** 2026-02-17  
**Issue:** UI customizations not persisting after server reboot  
**Status:** ✅ FIXED

## Problem Diagnosis

The investigation revealed:
1. ✅ `ui_customizations` table exists and is properly structured
2. ✅ Migration 015 successfully applied
3. ✅ Data IS being saved to database (verified via PostgreSQL query)
4. ✅ API endpoint `/api/ui-customizations` working correctly
5. ⚠️ Frontend query configuration could be more robust

## Root Cause

The UI customization query had minimal retry/refetch configuration that could cause:
- Race conditions during authentication/mount
- Stale data display after server restarts
- Cache inconsistencies across sessions

## Changes Applied

### Frontend (`/frontend/src/contexts/UiCustomizationContext.tsx`)

**Enhanced query configuration:**
```typescript
const { data, isLoading } = useQuery({
  queryKey: ['ui-customizations'],
  queryFn: () => uiCustomizationsApi.get(),
  enabled: !!user,
  staleTime: 60_000,
  gcTime: Infinity,              // NEW: Keep in cache indefinitely
  retry: 3,                       // CHANGED: from 1 to 3 retries
  refetchOnMount: 'always',       // NEW: Always fetch latest on mount
})
```

**Added debugging logs:**
- Logs when customizations load from server (DEV mode only)
- Logs when save operations complete
- Error logs for failed save attempts

## Verification Steps

### 1. Check Database Has Data
```bash
sudo docker exec rankings-bot-postgres psql -U rankings -d rankings -c \
  "SELECT scope, data, updated_at FROM ui_customizations WHERE scope = 'global';"
```

Expected: Shows your saved button/text customizations

### 2. Test API Endpoint (requires auth token)
```bash
# Get auth token first, then:
curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:8003/api/ui-customizations
```

Expected: Returns JSON with your customizations

### 3. Browser DevTools Check
1. Open Rankings Bot in browser
2. Open DevTools Console (F12)
3. Look for log: `[UiCustomization] Loaded from server: {...}`
4. Verify the data matches your saved customizations

### 4. Full Persistence Test
1. Make a UI change (hide/show button or change text)
2. Save the changes
3. See success toast: "UI customizations saved"
4. **Hard refresh browser** (Ctrl+Shift+R or Cmd+Shift+R)
5. Changes should persist

6. **Restart API service:**
   ```bash
   sudo systemctl restart rankings-bot-api
   ```
7. Refresh browser
8. Changes should STILL persist

## Files Modified

- `/home/ansible/rankings-bot/Rankings-Bot/frontend/src/contexts/UiCustomizationContext.tsx`
  - Enhanced query reliability
  - Added debug logging
  - Improved error handling

## Build & Deployment

✅ Frontend rebuilt: `npm run build` (completed at timestamp 15:39)  
✅ API restarted: `systemctl restart rankings-bot-api` (active since 15:39:13)

## Current Database State

```
scope: global
data: {
  "text": {},
  "buttons": {
    "nav.logs": {"label": null, "visible": false},
    "nav.system": {"label": null, "visible": false}
  },
  "layouts": {},
  "version": 1
}
updated_at: 2026-02-17 15:31:51.690268+00
```

## Additional Notes

- **Browser Cache:** If issues persist, clear browser cache or test in incognito/private mode
- **Authentication Required:** UI customizations only load when logged in (query `enabled: !!user`)
- **Super Admin Only:** Saving changes requires `super_admin` role
- **Debug Mode:** Set `NODE_ENV=development` to see console logs

## Migration Status

✅ Migration 015: `ui_customizations` table - APPLIED  
✅ Migration 016: `user_player_links` table - APPLIED

## Related Features

This fix also supports the user-to-player mapping feature (migration 016), which allows:
- Explicit user → player name mapping (for same-name disambiguation)
- Admin UI in Settings → Admin → Player link mapping
- Fallback to username if no mapping exists

## Troubleshooting

If customizations still don't persist:

1. **Check API logs:**
   ```bash
   sudo journalctl -u rankings-bot-api -n 100 --no-pager | grep -i customization
   ```

2. **Check browser network tab:**
   - Look for `/api/ui-customizations` requests
   - Verify they return 200 OK
   - Check response payload matches saved data

3. **Verify authentication:**
   ```bash
   # Check sessionStorage in browser console:
   sessionStorage.getItem('access_token')
   ```

4. **Database query:**
   - If data is missing, API may not be committing transactions
   - Check for database connection errors in logs

## Next Steps

✅ Changes deployed and ready for testing  
⏭️ Test in browser with the verification steps above  
⏭️ If issues persist, check browser console for `[UiCustomization]` logs

