import React, {useState, useEffect} from 'react';
import {
  View,
  Text,
  FlatList,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
} from 'react-native';

const SAMPLE_TOURNAMENTS = [
  {
    id: '1',
    name: 'Iron City Invitational VI 2025',
    date: '2025-01-15',
    location: 'Pittsburgh, PA',
    winner: 'Player A',
    participants: 64,
  },
  {
    id: '2',
    name: 'Colorado Classic 2025',
    date: '2025-02-20',
    location: 'Denver, CO',
    winner: 'Player B',
    participants: 48,
  },
  {
    id: '3',
    name: 'WPBA Championship 2024',
    date: '2024-12-10',
    location: 'Las Vegas, NV',
    winner: 'Player C',
    participants: 128,
  },
];

export default function TournamentHistoryScreen() {
  const [tournaments, setTournaments] = useState(SAMPLE_TOURNAMENTS);
  const [loading, setLoading] = useState(false);

  const renderTournamentItem = ({item}) => (
    <TouchableOpacity style={styles.tournamentItem}>
      <View style={styles.tournamentHeader}>
        <Text style={styles.tournamentName} numberOfLines={2}>
          {item.name}
        </Text>
        <Text style={styles.tournamentDate}>{item.date}</Text>
      </View>

      <View style={styles.tournamentDetails}>
        <Text style={styles.tournamentLocation}>📍 {item.location}</Text>
        <Text style={styles.tournamentWinner}>🏆 {item.winner}</Text>
        <Text style={styles.tournamentParticipants}>
          👥 {item.participants} players
        </Text>
      </View>
    </TouchableOpacity>
  );

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Tournament History</Text>
        <Text style={styles.subtitle}>
          View past tournament results and winners
        </Text>
      </View>

      {loading ? (
        <View style={styles.centerContainer}>
          <ActivityIndicator size="large" color="#38bdf8" />
          <Text style={styles.loadingText}>Loading tournaments...</Text>
        </View>
      ) : (
        <FlatList
          data={tournaments}
          renderItem={renderTournamentItem}
          keyExtractor={(item) => item.id}
          contentContainerStyle={styles.listContainer}
          showsVerticalScrollIndicator={false}
        />
      )}
    </View>
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
    textAlign: 'center',
  },
  centerContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    marginTop: 16,
    fontSize: 16,
    color: '#94a3b8',
  },
  listContainer: {
    padding: 16,
  },
  tournamentItem: {
    backgroundColor: '#1e293b',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#334155',
  },
  tournamentHeader: {
    marginBottom: 12,
  },
  tournamentName: {
    fontSize: 18,
    fontWeight: '600',
    color: '#f1f5f9',
    marginBottom: 4,
  },
  tournamentDate: {
    fontSize: 14,
    color: '#38bdf8',
    fontWeight: '500',
  },
  tournamentDetails: {
    gap: 8,
  },
  tournamentLocation: {
    fontSize: 14,
    color: '#94a3b8',
  },
  tournamentWinner: {
    fontSize: 14,
    color: '#fbbf24',
    fontWeight: '500',
  },
  tournamentParticipants: {
    fontSize: 14,
    color: '#94a3b8',
  },
});