# iOS Setup — Pure React Native (No Expo)

**Date:** March 15, 2026

---

## Overview

The mobile app is now a **pure React Native app** (no Expo) at the project root. It matches the web app's look and functionality but is touch-optimized for mobile.

## Structure

```
rankings-bot/
├── app.json                 # Basic config
├── babel.config.js          # Babel config
├── index.js                 # Entry point
├── metro.config.js          # Metro bundler config
├── package.json             # Dependencies (React Native CLI)
└── src/
    ├── App.tsx              # Main app with React Navigation
    ├── config.js            # API base URL
    ├── api/rankings.js      # API client
    └── screens/             # All screens
        ├── HomeScreen.js
        ├── RankingsScreen.js
        ├── SettingsScreen.js
        ├── TournamentHistoryScreen.js
        ├── PlayerPerformanceScreen.js
        └── HotStreakScreen.js
```

## Install Dependencies

```bash
cd /home/ansible/rankings-bot
npm install
```

## iOS Setup

### Prerequisites

- **macOS** with Xcode 15+
- **Node.js** 18+
- **React Native CLI** (installed via package.json)
- **CocoaPods** for iOS dependencies

### Setup Steps

1. **Install CocoaPods** (if not installed):
   ```bash
   sudo gem install cocoapods
   ```

2. **Create iOS project**:
   ```bash
   npx react-native init RankingsBot --skip-install
   # Or use existing ios/ directory if it exists
   ```

3. **Install iOS dependencies**:
   ```bash
   cd ios
   bundle install  # if Gemfile exists
   bundle exec pod install
   cd ..
   ```

4. **Start Metro bundler**:
   ```bash
   npm start
   ```

5. **Run on iOS Simulator**:
   ```bash
   npm run ios
   ```

## Android Setup (Optional)

### Prerequisites

- **Android Studio** with SDK
- **Java JDK** 17+

### Setup Steps

1. **Create Android project**:
   ```bash
   npx react-native init RankingsBot --skip-install
   ```

2. **Install Android dependencies**:
   ```bash
   cd android
   ./gradlew clean
   cd ..
   ```

3. **Run on Android**:
   ```bash
   npm run android
   ```

## What You Should See

### iOS Simulator

- **Bottom tabs**: Home, Rankings, Tournaments, Settings
- **Drawer navigation** from left edge swipe
- **Rankings screen**: Touch-optimized list with search and pagination
- **Visual design**: Matches web app (slate-950 background, sky-500 accents)

### Interface vs Web App

**Web App**: Complex table with sortable columns, advanced filtering, keyboard navigation.

**Mobile App**: Simple card-based list optimized for touch, pull-to-refresh, offline support.

## Troubleshooting

### iOS Build Issues

- **CocoaPods error**: Run `bundle exec pod install` in ios/
- **Xcode version**: Ensure Xcode 15+ and iOS Simulator
- **Metro port**: Ensure port 8081 is free

### Android Build Issues

- **SDK error**: Check Android Studio SDK location
- **Gradle error**: Run `./gradlew clean` in android/

### Common Issues

- **"Metro server not running"**: Run `npm start` first
- **"Device not found"**: Open iOS Simulator manually first
- **Dependencies**: Run `npm install` if modules missing

## Development

### Scripts

- `npm start` — Start Metro bundler
- `npm run ios` — Run iOS Simulator
- `npm run android` — Run Android device/emulator
- `npm run ios:setup` — Setup CocoaPods
- `npm run ios:open` — Open Xcode project

### Hot Reload

- Changes to JS/TS files reload automatically
- Native changes require rebuild (`npm run ios`)

## API Integration

- **Base URL**: Configured in `src/config.js`
- **Auth**: Uses same API as web app (`/api/v1/auth/login`)
- **Data**: Fetches from rankings endpoints (`/api/v1/rankings/*`)

## See Also

- [MOBILE_APP_MIGRATION.md](MOBILE_APP_MIGRATION.md) — Migration from Expo
- [IOS_SWIFT_NEXT_STEPS.md](IOS_SWIFT_NEXT_STEPS.md) — Native Swift alternative
- [WEB_AND_MOBILE_CHECKLIST.md](WEB_AND_MOBILE_CHECKLIST.md) — Web vs mobile differences