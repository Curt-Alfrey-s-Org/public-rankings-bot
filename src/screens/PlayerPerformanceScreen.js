import React, {useState, useEffect} from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
  TouchableOpacity,
} from 'react-native';
import {rankingsApi} from '../api/rankings';

export default function PlayerPerformanceScreen({route, navigation}) {
  const {playerName} = route.params || {};
  const [playerData, setPlayerData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (playerName) {
      loadPlayerData();
    }
  }, [playerName]);

  const loadPlayerData = async () => {
    try {
      setLoading(true);
      const data = await rankingsApi.getPlayer(playerName);
      setPlayerData(data);
    } catch (error) {
      console.error('Failed to load player data:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" color="#38bdf8" />
        <Text style={styles.loadingText}>Loading player data...</Text>
      </View>
    );
  }

  if (!playerData) {
    return (
      <View style={styles.centerContainer}>
        <Text style={styles.errorText}>Player data not found</Text>
        <TouchableOpacity
          style={styles.button}
          onPress={() => navigation.goBack()}>
          <Text style={styles.buttonText}>Go Back</Text>
        </TouchableOpacity>
      </View>
    );
  }

  const {wpba, wpa} = playerData;

  return (
    <ScrollView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>{playerName}</Text>
        <Text style={styles.subtitle}>Player Performance Analysis</Text>
      </View>

      {/* WPBA Rankings */}
      {wpba && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>WPBA Rankings</Text>
          <View style={styles.rankingCard}>
            <Text style={styles.rank}>Rank #{wpba.rank}</Text>
            <Text style={styles.points}>{wpba.points?.toFixed(2)} points</Text>
            {wpba.country && (
              <Text style={styles.country}>Country: {wpba.country}</Text>
            )}
            {wpba.fargo_rating && (
              <Text style={styles.fargo}>Fargo Rating: {wpba.fargo_rating}</Text>
            )}
          </View>
        </View>
      )}

      {/* WPA Rankings */}
      {wpa && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>WPA Rankings</Text>
          <View style={styles.rankingCard}>
            <Text style={styles.rank}>Rank #{wpa.rank}</Text>
            <Text style={styles.points}>{wpa.points?.toFixed(2)} points</Text>
            {wpa.country && (
              <Text style={styles.country}>Country: {wpa.country}</Text>
            )}
            {wpa.fargo_rating && (
              <Text style={styles.fargo}>Fargo Rating: {wpa.fargo_rating}</Text>
            )}
          </View>
        </View>
      )}

      {!wpba && !wpa && (
        <View style={styles.section}>
          <Text style={styles.noData}>No ranking data available</Text>
        </View>
      )}
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
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 16,
    color: '#94a3b8',
  },
  centerContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#0f172a',
  },
  loadingText: {
    marginTop: 16,
    fontSize: 16,
    color: '#94a3b8',
  },
  errorText: {
    fontSize: 18,
    color: '#f87171',
    marginBottom: 20,
  },
  button: {
    backgroundColor: '#38bdf8',
    paddingVertical: 12,
    paddingHorizontal: 24,
    borderRadius: 8,
  },
  buttonText: {
    color: '#ffffff',
    fontSize: 16,
    fontWeight: '600',
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
  rankingCard: {
    backgroundColor: '#1e293b',
    borderRadius: 12,
    padding: 16,
    borderWidth: 1,
    borderColor: '#334155',
  },
  rank: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#38bdf8',
    marginBottom: 8,
  },
  points: {
    fontSize: 18,
    color: '#f1f5f9',
    marginBottom: 8,
  },
  country: {
    fontSize: 16,
    color: '#94a3b8',
    marginBottom: 4,
  },
  fargo: {
    fontSize: 16,
    color: '#fbbf24',
  },
  noData: {
    fontSize: 16,
    color: '#64748b',
    textAlign: 'center',
  },
});