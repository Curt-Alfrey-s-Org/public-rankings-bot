import React, {useState, useEffect} from 'react';
import {
  View,
  Text,
  FlatList,
  TouchableOpacity,
  TextInput,
  StyleSheet,
  ActivityIndicator,
  RefreshControl,
  Alert,
} from 'react-native';
import {rankingsApi} from '../api/rankings';

const RANKING_SYSTEMS = [
  {key: 'WPBA_Women', label: '👑 WPBA Women (overall)', api: 'wpba'},
  {key: 'WPA_Women', label: '🌍 WPA Women (overall)', api: 'wpa-women'},
  {key: 'WPA_Men', label: '🎱 WPA Men (overall)', api: 'wpa-men'},
  {key: 'WPA_Heyball_Men', label: '🎯 Heyball Men (overall)', api: 'wpa-heyball-men'},
  {key: 'WPA_Heyball_Women', label: '🎯 Heyball Women (overall)', api: 'wpa-heyball-women'},
];

export default function RankingsScreen({navigation}) {
  const [selectedSystem, setSelectedSystem] = useState(RANKING_SYSTEMS[0]);
  const [rankings, setRankings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [page, setPage] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const [isOffline, setIsOffline] = useState(false);
  const [lastUpdated, setLastUpdated] = useState(null);

  useEffect(() => {
    loadRankings(true);
  }, [selectedSystem]);

  const loadRankings = async (reset = false) => {
    try {
      if (reset) {
        setLoading(true);
        setPage(0);
        setRankings([]);
        setHasMore(true);
        setIsOffline(false);
      }

      const currentPage = reset ? 0 : page;
      let response;

      switch (selectedSystem.api) {
        case 'wpba':
          response = await rankingsApi.getWPBA(100, currentPage * 100);
          break;
        case 'wpa-women':
          response = await rankingsApi.getWPAWomen(100, currentPage * 100);
          break;
        case 'wpa-men':
          response = await rankingsApi.getWPAMen(100, currentPage * 100);
          break;
        default:
          response = await rankingsApi.getWPBA(100, currentPage * 100);
      }

      if (reset) {
        setRankings(response.rankings || []);
      } else {
        setRankings(prev => [...prev, ...(response.rankings || [])]);
      }

      setPage(currentPage + 1);
      setHasMore((response.rankings || []).length === 100);
      setLastUpdated(new Date().toISOString());
    } catch (error) {
      console.error('Failed to load rankings:', error);
      setIsOffline(true);
      Alert.alert('Error', 'Failed to load rankings. Check your connection.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const onRefresh = () => {
    setRefreshing(true);
    loadRankings(true);
  };

  const filteredRankings = rankings.filter(ranking =>
    ranking.name?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const renderRankingItem = ({item, index}) => (
    <TouchableOpacity
      style={styles.rankingItem}
      onPress={() => navigation.navigate('PlayerPerformance', {playerName: item.name})}>
      <View style={styles.rankContainer}>
        <Text style={styles.rank}>#{item.rank}</Text>
      </View>
      <View style={styles.playerInfo}>
        <Text style={styles.playerName} numberOfLines={1}>
          {item.name}
        </Text>
        {item.country && (
          <Text style={styles.playerDetails}>
            {item.country} • {item.points?.toFixed(2) || '0.00'} pts
          </Text>
        )}
        {item.license_number && (
          <Text style={styles.license}>{item.license_number}</Text>
        )}
        {item.fargo_rating && (
          <Text style={styles.fargoRating}>Fargo: {item.fargo_rating}</Text>
        )}
      </View>
    </TouchableOpacity>
  );

  const renderSystemSelector = () => (
    <View style={styles.systemSelector}>
      <FlatList
        horizontal
        data={RANKING_SYSTEMS}
        keyExtractor={(item) => item.key}
        showsHorizontalScrollIndicator={false}
        renderItem={({item}) => (
          <TouchableOpacity
            style={[
              styles.systemButton,
              selectedSystem.key === item.key && styles.systemButtonActive
            ]}
            onPress={() => {
              setSelectedSystem(item);
              setPage(0);
            }}>
            <Text style={[
              styles.systemButtonText,
              selectedSystem.key === item.key && styles.systemButtonTextActive
            ]}>
              {item.label}
            </Text>
          </TouchableOpacity>
        )}
      />
    </View>
  );

  return (
    <View style={styles.container}>
      {renderSystemSelector()}

      <View style={styles.searchContainer}>
        <TextInput
          style={styles.searchInput}
          placeholder="Search players..."
          placeholderTextColor="#94a3b8"
          value={searchQuery}
          onChangeText={setSearchQuery}
        />
      </View>

      <View style={styles.statusContainer}>
        <Text style={styles.resultsCount}>
          {filteredRankings.length} players • {selectedSystem.label}
        </Text>
        {isOffline && (
          <View style={styles.offlineIndicator}>
            <Text style={styles.offlineText}>📴 Offline</Text>
          </View>
        )}
        {lastUpdated && (
          <Text style={styles.lastUpdatedText}>
            Updated: {new Date(lastUpdated).toLocaleTimeString()}
          </Text>
        )}
      </View>

      {loading && rankings.length === 0 ? (
        <View style={styles.centerContainer}>
          <ActivityIndicator size="large" color="#38bdf8" />
          <Text style={styles.loadingText}>Loading rankings...</Text>
        </View>
      ) : (
        <FlatList
          data={filteredRankings}
          renderItem={renderRankingItem}
          keyExtractor={(item, index) => `${item.name}-${item.rank}-${index}`}
          onEndReached={() => hasMore && !loading && loadRankings()}
          onEndReachedThreshold={0.5}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={onRefresh}
              colors={['#38bdf8']}
              tintColor="#38bdf8"
            />
          }
          ListFooterComponent={
            loading && rankings.length > 0 ? (
              <View style={styles.footerLoader}>
                <ActivityIndicator size="small" color="#38bdf8" />
                <Text style={styles.footerText}>Loading more...</Text>
              </View>
            ) : null
          }
          ListEmptyComponent={
            !loading && (
              <View style={styles.emptyContainer}>
                <Text style={styles.emptyText}>
                  {isOffline ? 'No cached rankings available' : 'No rankings found'}
                </Text>
                <Text style={styles.emptyHint}>
                  {isOffline ? 'Check your connection' : 'Pull down to refresh'}
                </Text>
              </View>
            )
          }
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
  systemSelector: {
    paddingHorizontal: 16,
    paddingVertical: 12,
    backgroundColor: '#1e293b',
  },
  systemButton: {
    paddingHorizontal: 12,
    paddingVertical: 8,
    marginRight: 8,
    borderRadius: 20,
    backgroundColor: '#334155',
    minWidth: 120,
    alignItems: 'center',
  },
  systemButtonActive: {
    backgroundColor: '#38bdf8',
  },
  systemButtonText: {
    fontSize: 14,
    color: '#cbd5e1',
    fontWeight: '500',
  },
  systemButtonTextActive: {
    color: '#ffffff',
  },
  searchContainer: {
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  searchInput: {
    backgroundColor: '#1e293b',
    borderRadius: 8,
    paddingHorizontal: 16,
    paddingVertical: 12,
    color: '#f1f5f9',
    fontSize: 16,
  },
  statusContainer: {
    paddingHorizontal: 16,
    paddingBottom: 8,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  resultsCount: {
    fontSize: 14,
    color: '#94a3b8',
  },
  offlineIndicator: {
    backgroundColor: '#dc2626',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 12,
  },
  offlineText: {
    fontSize: 12,
    color: '#ffffff',
    fontWeight: '500',
  },
  lastUpdatedText: {
    fontSize: 12,
    color: '#94a3b8',
  },
  centerContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingVertical: 48,
  },
  loadingText: {
    marginTop: 16,
    fontSize: 16,
    color: '#94a3b8',
  },
  rankingItem: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#334155',
    backgroundColor: '#0f172a',
  },
  rankContainer: {
    width: 60,
    alignItems: 'center',
  },
  rank: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#38bdf8',
  },
  playerInfo: {
    flex: 1,
  },
  playerName: {
    fontSize: 16,
    color: '#f1f5f9',
    fontWeight: '500',
    marginBottom: 4,
  },
  playerDetails: {
    fontSize: 14,
    color: '#94a3b8',
    marginBottom: 2,
  },
  license: {
    fontSize: 12,
    color: '#64748b',
    fontFamily: 'monospace',
  },
  fargoRating: {
    fontSize: 12,
    color: '#fbbf24',
    marginTop: 2,
  },
  footerLoader: {
    paddingVertical: 16,
    alignItems: 'center',
  },
  footerText: {
    marginTop: 8,
    fontSize: 14,
    color: '#94a3b8',
  },
  emptyContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingVertical: 48,
  },
  emptyText: {
    fontSize: 18,
    color: '#94a3b8',
    textAlign: 'center',
    marginBottom: 8,
  },
  emptyHint: {
    fontSize: 14,
    color: '#64748b',
    textAlign: 'center',
  },
});