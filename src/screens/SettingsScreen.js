import React from 'react';
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  StyleSheet,
  Linking,
} from 'react-native';

export default function SettingsScreen() {
  return (
    <ScrollView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Settings</Text>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>About Rankings Bot</Text>
        <Text style={styles.description}>
          This app shows Rankings and Tournament data. For the full site (Home, Tournaments, Movement, Movement, AI Coach, Head-to-Head, and more), open the website.
        </Text>
      </View>

      <View style={styles.section}>
        <TouchableOpacity
          style={styles.button}
          onPress={() => Linking.openURL('https://www.probilliardssoftware.com')}>
          <Text style={styles.buttonText}>🌐 Open Full Website</Text>
        </TouchableOpacity>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Features Available</Text>
        <Text style={styles.feature}>• Live WPBA & WPA Rankings</Text>
        <Text style={styles.feature}>• Tournament History</Text>
        <Text style={styles.feature}>• Player Performance Analysis</Text>
        <Text style={styles.feature}>• Hot Streak Tracking</Text>
        <Text style={styles.feature}>• Fargo Rating Integration</Text>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>App Version</Text>
        <Text style={styles.version}>Rankings Bot Mobile v1.0.0</Text>
        <Text style={styles.versionSubtext}>Built with React Native</Text>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0f172a',
  },
  header: {
    padding: 24,
    alignItems: 'center',
  },
  title: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#f1f5f9',
  },
  section: {
    paddingHorizontal: 24,
    paddingVertical: 16,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#f1f5f9',
    marginBottom: 12,
  },
  description: {
    fontSize: 16,
    color: '#94a3b8',
    lineHeight: 24,
  },
  button: {
    backgroundColor: '#38bdf8',
    paddingVertical: 16,
    paddingHorizontal: 24,
    borderRadius: 8,
    alignItems: 'center',
  },
  buttonText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#ffffff',
  },
  feature: {
    fontSize: 16,
    color: '#cbd5e1',
    marginBottom: 8,
    lineHeight: 24,
  },
  version: {
    fontSize: 16,
    color: '#f1f5f9',
    fontWeight: '500',
  },
  versionSubtext: {
    fontSize: 14,
    color: '#64748b',
    marginTop: 4,
  },
});