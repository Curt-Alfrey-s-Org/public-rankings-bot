import React from 'react';
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  StyleSheet,
  Linking,
} from 'react-native';

export default function HomeScreen({navigation}) {
  return (
    <ScrollView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Pro Billiards Software</Text>
        <Text style={styles.subtitle}>
          Player AI Coach, WPBA/WPA Rankings, Tournament Management, Fargo Ratings...and more
        </Text>
      </View>

      <View style={styles.statsGrid}>
        <TouchableOpacity
          style={styles.statCard}
          onPress={() => navigation.navigate('Rankings')}>
          <Text style={styles.statEmoji}>🏆</Text>
          <Text style={styles.statTitle}>Rankings</Text>
          <Text style={styles.statDescription}>
            Check current WPBA and WPA player rankings with live updates
          </Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={styles.statCard}
          onPress={() => navigation.navigate('Tournaments')}>
          <Text style={styles.statEmoji}>🏟️</Text>
          <Text style={styles.statTitle}>Tournaments</Text>
          <Text style={styles.statDescription}>
            View tournament history and results
          </Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={styles.statCard}
          onPress={() => navigation.navigate('HotStreak')}>
          <Text style={styles.statEmoji}>🔥</Text>
          <Text style={styles.statTitle}>Hot Streak</Text>
          <Text style={styles.statDescription}>
            Players on the rise with improving tournament placements
          </Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={styles.statCard}
          onPress={() => Linking.openURL('https://www.probilliardssoftware.com')}>
          <Text style={styles.statEmoji}>🌐</Text>
          <Text style={styles.statTitle}>Full Website</Text>
          <Text style={styles.statDescription}>
            Access tournament management, AI coach, and all features
          </Text>
        </TouchableOpacity>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Recent Updates</Text>
        <Text style={styles.sectionText}>
          • WPBA Women rankings refreshed with latest tournament results
        </Text>
        <Text style={styles.sectionText}>
          • New AI-powered player performance analysis
        </Text>
        <Text style={styles.sectionText}>
          • Enhanced tournament bracket management
        </Text>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Features</Text>
        <Text style={styles.sectionText}>• Live WPBA & WPA Rankings</Text>
        <Text style={styles.sectionText}>• Tournament History & Results</Text>
        <Text style={styles.sectionText}>• Player Performance Tracking</Text>
        <Text style={styles.sectionText}>• Fargo Rating Integration</Text>
        <Text style={styles.sectionText}>• Hot Streak Analysis</Text>
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
    fontSize: 28,
    fontWeight: 'bold',
    color: '#f1f5f9',
    textAlign: 'center',
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 16,
    color: '#94a3b8',
    textAlign: 'center',
    lineHeight: 24,
  },
  statsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    paddingHorizontal: 16,
    gap: 16,
  },
  statCard: {
    flex: 1,
    minWidth: 160,
    backgroundColor: '#1e293b',
    borderRadius: 12,
    padding: 16,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#334155',
  },
  statEmoji: {
    fontSize: 32,
    marginBottom: 8,
  },
  statTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#f1f5f9',
    marginBottom: 8,
    textAlign: 'center',
  },
  statDescription: {
    fontSize: 14,
    color: '#94a3b8',
    textAlign: 'center',
    lineHeight: 20,
  },
  section: {
    padding: 24,
  },
  sectionTitle: {
    fontSize: 20,
    fontWeight: '600',
    color: '#f1f5f9',
    marginBottom: 16,
  },
  sectionText: {
    fontSize: 16,
    color: '#cbd5e1',
    marginBottom: 8,
    lineHeight: 24,
  },
});