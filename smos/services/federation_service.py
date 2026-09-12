from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from smos.core.interfaces import Observable
from smos.models.ecology import FederatedNode, FederatedSubscription, ProvenanceRecord
from smos.models.models import MemoryNode, EpistemicStatus
from smos.models.epistemic import IntellectualCluster

class FederationService(Observable):
    """
    Service for managing multi-node federation, subscriptions, knowledge sync,
    provenance preservation, and epistemic sovereignty boundaries.
    """
    def __init__(self, db: Session):
        self.db = db

    # Node Management & Federation
    def register_node(
        self,
        name: str,
        endpoint_url: str,
        trust_score: float = 1.0,
        sovereignty_level: str = "HIGH",
        consensus_priority: str = "VERIFIED_SCIENCE"
    ) -> FederatedNode:
        """Register a new remote node in the federated network."""
        existing = self.db.query(FederatedNode).filter(FederatedNode.endpoint_url == endpoint_url).first()
        if existing:
            existing.name = name
            existing.trust_score = trust_score
            existing.sovereignty_level = sovereignty_level
            existing.consensus_priority = consensus_priority
            existing.status = "ACTIVE"
            self.db.commit()
            self.db.refresh(existing)
            return existing

        node = FederatedNode(
            name=name,
            endpoint_url=endpoint_url,
            trust_score=trust_score,
            sovereignty_level=sovereignty_level,
            consensus_priority=consensus_priority,
            status="ACTIVE"
        )
        self.db.add(node)
        self.db.commit()
        self.db.refresh(node)
        return node

    def list_nodes(self, active_only: bool = True) -> List[FederatedNode]:
        """List all federated nodes registered in the system."""
        query = self.db.query(FederatedNode)
        if active_only:
            query = query.filter(FederatedNode.status == "ACTIVE")
        return query.all()

    def get_node_status(self, node_id: int) -> Optional[Dict[str, Any]]:
        """Get the status, subscriptions, and metrics of a federated node."""
        node = self.db.get(FederatedNode, node_id)
        if not node:
            return None

        subscriptions = self.db.query(FederatedSubscription).filter(
            FederatedSubscription.node_id == node_id,
            FederatedSubscription.is_active == True
        ).all()

        return {
            "id": node.id,
            "name": node.name,
            "endpoint_url": node.endpoint_url,
            "trust_score": node.trust_score,
            "sovereignty_level": node.sovereignty_level,
            "consensus_priority": node.consensus_priority,
            "status": node.status,
            "active_subscriptions_count": len(subscriptions)
        }

    # Subscriptions
    def subscribe_cluster(
        self,
        node_id: int,
        cluster_id: Optional[int] = None,
        topic: Optional[str] = None,
        consensus_filter: Optional[str] = None
    ) -> FederatedSubscription:
        """Subscribe to a cluster or topic on a remote node with consensus level filtering."""
        sub = FederatedSubscription(
            node_id=node_id,
            cluster_id=cluster_id,
            topic=topic,
            consensus_filter=consensus_filter or "Verified",
            is_active=True
        )
        self.db.add(sub)
        self.db.commit()
        self.db.refresh(sub)
        return sub

    def unsubscribe_cluster(self, subscription_id: int) -> bool:
        """Deactivate a cluster subscription."""
        sub = self.db.get(FederatedSubscription, subscription_id)
        if not sub:
            return False
        sub.is_active = False
        self.db.commit()
        return True

    # Knowledge Synchronization & Sovereignty Boundary Preservation
    def export_knowledge_payload(
        self,
        cluster_id: Optional[int] = None,
        min_epistemic_status: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Export a knowledge payload for federation sharing.
        Preserves provenance records and respects epistemic filters.
        """
        query = self.db.query(MemoryNode)
        if cluster_id:
            # Filter memory nodes associated with the cluster
            query = query.filter(MemoryNode.cluster_ids.contains([cluster_id]))

        nodes = query.all()
        exported_nodes = []

        for node in nodes:
            # If epistemic filter is supplied, check status matching
            if min_epistemic_status and node.epistemic_status:
                if str(node.epistemic_status.value).upper() != min_epistemic_status.upper():
                    continue

            # Fetch provenance record if available
            prov = self.db.query(ProvenanceRecord).filter(ProvenanceRecord.node_id == node.id).first()
            prov_data = None
            if prov:
                prov_data = {
                    "created_by_id": prov.created_by_id,
                    "contributors": prov.contributors or [],
                    "evidence_links": prov.evidence_links or [],
                    "revision_history": prov.revision_history or []
                }

            exported_nodes.append({
                "local_node_id": node.id,
                "content": node.content,
                "type": node.type.value if hasattr(node.type, "value") else str(node.type),
                "epistemic_status": node.epistemic_status.value if hasattr(node.epistemic_status, "value") else str(node.epistemic_status),
                "provenance": prov_data,
                "tags": node.tags or []
            })

        return {
            "source_instance": "Co-SMOS-Node",
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "count": len(exported_nodes),
            "items": exported_nodes
        }

    def sync_knowledge_from_node(
        self,
        source_node_id: int,
        knowledge_payload: Dict[str, Any],
        target_timeline_id: int,
        target_owner_id: int
    ) -> Dict[str, Any]:
        """
        Ingest and synchronize external knowledge payload from a federated node while maintaining
        provenance, preserving epistemic boundaries, and non-destructive integration.
        """
        fed_node = self.db.get(FederatedNode, source_node_id)
        if not fed_node:
            raise ValueError(f"Federated node {source_node_id} not found")

        items = knowledge_payload.get("items", [])
        synced_count = 0
        skipped_count = 0

        for item in items:
            raw_epistemic = item.get("epistemic_status", "Unverified")
            
            # Preserve epistemic boundaries: ensure consensus alignment or preserve layer
            try:
                ep_status = EpistemicStatus(raw_epistemic)
            except ValueError:
                ep_status = EpistemicStatus.UNVERIFIED

            # Create new memory node locally with origin metadata tagged
            node_content = f"[Federated: {fed_node.name}] {item.get('content', '')}"
            m_node = MemoryNode(
                content=node_content,
                owner_id=target_owner_id,
                timeline_id=target_timeline_id,
                epistemic_status=ep_status,
                tags=(item.get("tags") or []) + [f"federated:{fed_node.name}"]
            )
            self.db.add(m_node)
            self.db.commit()
            self.db.refresh(m_node)

            # Recreate ProvenanceRecord to preserve origin history
            prov_info = item.get("provenance")
            evidence = (prov_info.get("evidence_links") if prov_info else []) or [f"federated_origin:{fed_node.endpoint_url}"]
            contributors = (prov_info.get("contributors") if prov_info else []) or []
            
            prov_rec = ProvenanceRecord(
                node_id=m_node.id,
                created_by_id=prov_info.get("created_by_id") if prov_info else None,
                contributors=contributors,
                evidence_links=evidence,
                revision_history=[{"event": "federated_sync", "source_node": fed_node.name}]
            )
            self.db.add(prov_rec)
            self.db.commit()
            synced_count += 1

        return {
            "source_node_id": source_node_id,
            "status": "COMPLETED",
            "synced_items": synced_count,
            "skipped_items": skipped_count
        }

    # Sovereignty Methods
    def evaluate_sovereignty_policy(self, node_id: int) -> Dict[str, Any]:
        """Evaluate local sovereignty principles and policies regarding a federated node."""
        node = self.db.get(FederatedNode, node_id)
        if not node:
            return {"sovereignty_compliant": False, "reason": "Node not found"}

        principles = self.check_sovereignty_principles()
        is_sovereign = (
            node.trust_score >= 0.3 and
            node.status == "ACTIVE" and
            principles.get("avoid_single_point_of_control", True)
        )

        return {
            "node_id": node_id,
            "sovereignty_compliant": is_sovereign,
            "sovereignty_level": node.sovereignty_level,
            "consensus_priority": node.consensus_priority,
            "principles": principles
        }

    def check_sovereignty_principles(self) -> Dict[str, Any]:
        """Return core sovereignty principles governing the federation."""
        return {
            "avoid_single_point_of_control": True,
            "preserve_plurality": True,
            "preserve_dissent": True,
            "epistemic_autonomy": True,
            "provenance_transparency": True
        }

    # Observable interface
    def get_health_metrics(self) -> Dict[str, Any]:
        total_nodes = self.db.query(FederatedNode).count()
        active_nodes = self.db.query(FederatedNode).filter(FederatedNode.status == "ACTIVE").count()
        total_subscriptions = self.db.query(FederatedSubscription).filter(FederatedSubscription.is_active == True).count()

        health_score = (active_nodes / total_nodes) if total_nodes > 0 else 1.0

        return {
            "health": round(health_score, 4),
            "total_nodes": total_nodes,
            "active_nodes": active_nodes,
            "active_subscriptions": total_subscriptions
        }

    def get_evolution_summary(self) -> List[Dict[str, Any]]:
        return [{"event": "Federation topology updated", "subsystem": "FederationService"}]
