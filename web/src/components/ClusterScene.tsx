import { Canvas } from '@react-three/fiber';
import { Billboard, Html, OrbitControls, PerspectiveCamera, Stars } from '@react-three/drei';
import { Bloom, EffectComposer } from '@react-three/postprocessing';
import { Suspense, useMemo } from 'react';
import * as THREE from 'three';
import { PaperPoint } from '../types';
import { getClusterColor } from '../utils/color';

const GLOW_TEXTURE_CACHE = new Map<number, THREE.CanvasTexture>();
const GLOW_MATERIAL_CACHE = new Map<number, THREE.SpriteMaterial>();
const noopRaycast: THREE.Object3D['raycast'] = () => {};

const createGlowTexture = (color: THREE.Color) => {
  const size = 256;
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const context = canvas.getContext('2d');

  if (!context) {
    throw new Error('Unable to acquire 2D context for glow texture.');
  }

  const gradient = context.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
  gradient.addColorStop(0, color.clone().multiplyScalar(1.15).getStyle());
  gradient.addColorStop(0.35, color.clone().multiplyScalar(0.85).getStyle());
  gradient.addColorStop(1, 'rgba(0, 0, 0, 0)');

  context.fillStyle = gradient;
  context.fillRect(0, 0, size, size);

  const texture = new THREE.CanvasTexture(canvas);
  texture.encoding = THREE.sRGBEncoding;
  texture.anisotropy = 4;
  texture.needsUpdate = true;
  return texture;
};

const getGlowMaterial = (clusterId: number, color: THREE.Color) => {
  const cached = GLOW_MATERIAL_CACHE.get(clusterId);
  if (cached) {
    return cached;
  }

  const texture = createGlowTexture(color);
  const material = new THREE.SpriteMaterial({
    map: texture,
    transparent: true,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
    depthTest: false,
    opacity: 0.32
  });

  GLOW_TEXTURE_CACHE.set(clusterId, texture);
  GLOW_MATERIAL_CACHE.set(clusterId, material);
  return material;
};

type HoverPayload = {
  paper: PaperPoint | null;
  screenPosition?: { x: number; y: number };
};

type ClusterSceneProps = {
  papers: PaperPoint[];
  hoveringPaperId: string | null;
  hoveringClusterId: number | null;
  pinnedPaperIds: Set<string>;
  onHoverChange: (payload: HoverPayload) => void;
  onTogglePin: (paper: PaperPoint) => void;
  onBackgroundClick: () => void;
};

const computeSceneMetrics = (papers: PaperPoint[]) => {
  if (papers.length === 0) {
    const center = new THREE.Vector3(0, 0, 0);
    return { center, radius: 60 };
  }

  const box = new THREE.Box3();
  papers.forEach((paper) => {
    box.expandByPoint(new THREE.Vector3(...paper.coordinates));
  });

  const size = new THREE.Vector3();
  box.getSize(size);
  const center = new THREE.Vector3();
  box.getCenter(center);

  const maxDimension = Math.max(size.x, size.y, size.z);
  const radius = Math.max(14, maxDimension * 0.55 + 6);

  return { center, radius };
};

const PaperPointMesh = ({
  paper,
  hovered,
  pinned,
  clusterHighlighted,
  onHoverChange,
  onTogglePin
}: {
  paper: PaperPoint;
  hovered: boolean;
  pinned: boolean;
  clusterHighlighted: boolean;
  onHoverChange: (payload: HoverPayload) => void;
  onTogglePin: (paper: PaperPoint) => void;
}) => {
  const color = useMemo(() => getClusterColor(paper.clusterId).clone(), [paper.clusterId]);
  const glowMaterial = useMemo(
    () => getGlowMaterial(paper.clusterId, color.clone()),
    [paper.clusterId, color]
  );

  let groupScale = 1;
  let coreScale = 0.2;
  let emissiveIntensity = 0.42;
  let materialOpacity = 0.7;
  let haloScale = 0.3;

  if (clusterHighlighted) {
    groupScale = 1.08;
    coreScale = 0.22;
    emissiveIntensity = 0.55;
    materialOpacity = 0.9;
    haloScale = 0.32;
  }

  if (hovered) {
    groupScale = 1.18;
    coreScale = 0.22;
    emissiveIntensity = 0.68;
    materialOpacity = 0.9;
    haloScale = 0.34;
  }

  if (pinned) {
    groupScale = 1.28;
    coreScale = 0.3;
    emissiveIntensity = 0.85;
    materialOpacity = 0.9;
    haloScale = 0.36;
  }

  return (
    <group position={paper.coordinates} scale={groupScale}>
      <mesh
        scale={coreScale}
        onPointerOver={(event) => {
          event.stopPropagation();
          onHoverChange({
            paper,
            screenPosition: { x: event.clientX, y: event.clientY }
          });
        }}
        onPointerMove={(event) => {
          event.stopPropagation();
          onHoverChange({
            paper,
            screenPosition: { x: event.clientX, y: event.clientY }
          });
        }}
        onPointerOut={(event) => {
          event.stopPropagation();
          onHoverChange({ paper: null });
        }}
        onClick={(event) => {
          event.stopPropagation();
          onTogglePin(paper);
        }}
      >
        <sphereGeometry args={[0.22, 32, 32]} />
        <meshStandardMaterial
          transparent
          opacity={materialOpacity}
          color={color}
          emissive={color.clone().multiplyScalar(0.4)}
          emissiveIntensity={emissiveIntensity}
          roughness={0.25}
          metalness={0.1}
        />
      </mesh>
      <Billboard>
        <sprite
          material={glowMaterial}
          scale={[haloScale, haloScale, haloScale]}
          renderOrder={-1}
          raycast={noopRaycast}
        />
      </Billboard>
      {/* {(pinned || hovered) && (
        <Html
          distanceFactor={18}
          occlude
          style={{
            padding: '10px 12px',
            borderRadius: '12px',
            border: '1px solid rgba(120, 148, 255, 0.4)',
            background: 'rgba(12, 18, 38, 0.85)',
            color: '#f7f9ff',
            fontSize: '0.75rem',
            letterSpacing: '0.02em',
            boxShadow: '0 12px 28px rgba(12, 18, 44, 0.45)',
            pointerEvents: 'none'
          }}
          position={[0, 3.4, 0]}
        >
          {paper.title}
        </Html>
      )} */}
    </group>
  );
};

const ClusterScene = ({
  papers,
  hoveringPaperId,
  hoveringClusterId,
  pinnedPaperIds,
  onHoverChange,
  onTogglePin,
  onBackgroundClick
}: ClusterSceneProps) => {
  const { center, radius } = useMemo(() => computeSceneMetrics(papers), [papers]);

  const cameraPosition = useMemo(() => {
    const offset = Math.max(6, radius * 0.75 + 1);
    return new THREE.Vector3(center.x + offset, center.y + offset * 0.1, center.z + offset * 0.1);
  }, [center, radius]);

  return (
    <Canvas
      dpr={[1, 2]}
      gl={{ antialias: true, alpha: false }}
      camera={{ position: cameraPosition.toArray(), fov: 48 }}
      style={{ width: '100%', height: '100%' }}
      onPointerMissed={(event) => {
        if (event.button === 0) {
          onBackgroundClick();
        }
      }}
    >
      <color attach="background" args={['#02030a']} />
      <fog attach="fog" args={['#02030a', radius * 1.8, radius * 4.4]} />
      <ambientLight intensity={0.18} />
      <pointLight position={[40, 60, 80]} intensity={1.5} color="#a855f7" />
      <pointLight position={[-80, -40, -60]} intensity={1.1} color="#2563eb" />

      <Suspense fallback={null}>
        <PerspectiveCamera makeDefault position={cameraPosition.toArray()} />
        <OrbitControls
          target={center.toArray() as [number, number, number]}
          enableDamping
          dampingFactor={0.045}
          autoRotate={hoveringPaperId === null}
          autoRotateSpeed={0.35}
          minDistance={Math.max(4, radius * 0.2)}
          maxDistance={radius * 6.5}
          maxPolarAngle={Math.PI}
        />
        <Stars
          radius={radius * 4}
          depth={radius * 6}
          count={6000}
          factor={radius * 0.08}
          saturation={0}
          fade
        />
        {papers.map((paper) => (
          <PaperPointMesh
            key={paper.paperId}
            paper={paper}
            hovered={hoveringPaperId === paper.paperId}
            pinned={pinnedPaperIds.has(paper.paperId)}
            clusterHighlighted={
              hoveringClusterId !== null && paper.clusterId === hoveringClusterId
            }
            onHoverChange={onHoverChange}
            onTogglePin={onTogglePin}
          />
        ))}

        <EffectComposer multisampling={4}>
          <Bloom
            luminanceThreshold={0.2}
            luminanceSmoothing={0.55}
            intensity={1.2}
          />
        </EffectComposer>
      </Suspense>
    </Canvas>
  );
};

export default ClusterScene;
