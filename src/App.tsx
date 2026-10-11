import React from 'react';
import {StatusBar} from 'react-native';
import {SafeAreaProvider} from 'react-native-safe-area-context';
import {NavigationContainer} from '@react-navigation/native';
import {createBottomTabNavigator} from '@react-navigation/bottom-tabs';
import {createDrawerNavigator} from '@react-navigation/drawer';
import {createNativeStackNavigator} from '@react-navigation/native-stack';

import RankingsScreen from './screens/RankingsScreen';
import HomeScreen from './screens/HomeScreen';
import SettingsScreen from './screens/SettingsScreen';
import TournamentHistoryScreen from './screens/TournamentHistoryScreen';
import PlayerPerformanceScreen from './screens/PlayerPerformanceScreen';
import HotStreakScreen from './screens/HotStreakScreen';

const Tab = createBottomTabNavigator();
const Drawer = createDrawerNavigator();
const Stack = createNativeStackNavigator();

function RankingsStack() {
  return (
    <Stack.Navigator screenOptions={{headerShown: false}}>
      <Stack.Screen name="RankingsMain" component={RankingsScreen} />
      <Stack.Screen name="PlayerPerformance" component={PlayerPerformanceScreen} />
    </Stack.Navigator>
  );
}

function MainTabs() {
  return (
    <Tab.Navigator
      screenOptions={{
        tabBarStyle: {
          backgroundColor: '#0f172a',
          borderTopColor: '#334155',
        },
        tabBarActiveTintColor: '#38bdf8',
        tabBarInactiveTintColor: '#94a3b8',
        headerStyle: {
          backgroundColor: '#0f172a',
        },
        headerTintColor: '#f1f5f9',
      }}>
      <Tab.Screen
        name="Home"
        component={HomeScreen}
        options={{
          title: 'Home',
          tabBarIcon: ({color, size}) => (
            <Text style={{color, fontSize: size}}>🏠</Text>
          ),
        }}
      />
      <Tab.Screen
        name="Rankings"
        component={RankingsStack}
        options={{
          title: 'Rankings',
          headerShown: false,
          tabBarIcon: ({color, size}) => (
            <Text style={{color, fontSize: size}}>🏆</Text>
          ),
        }}
      />
      <Tab.Screen
        name="Tournaments"
        component={TournamentHistoryScreen}
        options={{
          title: 'Tournaments',
          tabBarIcon: ({color, size}) => (
            <Text style={{color, fontSize: size}}>🏟️</Text>
          ),
        }}
      />
      <Tab.Screen
        name="HotStreak"
        component={HotStreakScreen}
        options={{
          title: 'Hot Streak',
          tabBarIcon: ({color, size}) => (
            <Text style={{color, fontSize: size}}>🔥</Text>
          ),
        }}
      />
      <Tab.Screen
        name="Settings"
        component={SettingsScreen}
        options={{
          title: 'Settings',
          tabBarIcon: ({color, size}) => (
            <Text style={{color, fontSize: size}}>⚙️</Text>
          ),
        }}
      />
    </Tab.Navigator>
  );
}

function AppContent() {
  return (
    <NavigationContainer>
      <Drawer.Navigator
        screenOptions={{
          drawerStyle: {
            backgroundColor: '#0f172a',
          },
          drawerActiveTintColor: '#38bdf8',
          drawerInactiveTintColor: '#94a3b8',
          headerStyle: {
            backgroundColor: '#0f172a',
          },
          headerTintColor: '#f1f5f9',
        }}>
        <Drawer.Screen name="Main" component={MainTabs} options={{title: 'Rankings Bot'}} />
      </Drawer.Navigator>
    </NavigationContainer>
  );
}

export default function App() {
  return (
    <SafeAreaProvider>
      <AppContent />
      <StatusBar style="light" backgroundColor="#0f172a" />
    </SafeAreaProvider>
  );
}