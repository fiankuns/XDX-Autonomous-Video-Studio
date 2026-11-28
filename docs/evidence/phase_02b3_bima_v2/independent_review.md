# Independent Visual Review: Bima v2 (Blender) vs Blueprint
Reviewer: independent visual_critic (not the producer). Inputs: compare sheet, 6 n_*.png renders, 6 blueprint PNGs, style bible xdx_pixar_stylized_3d_v1, gate_report.json.
Blueprint ghosting (doubled arms/torso in side/3-4 views) was ignored.

## Verdict: REJECT (revise and resubmit; the design reads correctly, but it is not yet production quality)
The automated gate reports PASS_AUTOMATED_CHECKS (front IoU 0.85). That pass is real but only covers geometry. In the images, the model looks like a
simplified toy or mannequin rather than the Pixar-like blueprint: thin stick limbs, hands without fingers, tiny shoes, baggy tube trousers,
stuck-on facial features, and a bald patch on the back of the head.

## Scores (0-10)
1. Overall likeness 5/10: the curly black hair, yellow "kalian tau gak?" tee, white trousers and navy shoes are all there, so you can tell it is Bima, but the body build and surface quality do not match.
2. Proportions 5/10: head-to-height looks about right (~0.22), but the arms are uniform thin cylinders, the torso is a narrow tube, and the shoes are about half the blueprint size (front, back).
3. Face 5/10: eyes, brows and open smile are close to the blueprint. The nose is a stuck-on ball, the blush is flat speckled salmon discs instead of soft SSS flush, the ears are almost invisible, and in profile the eye, brow, nose and lips stick out past the head outline (right, left).
4. Hair 6/10: good volume and curl clumps, and the silhouette is close (hair error 0.04). The surface is grainy noise with no soft specular sheen. The forelock curl over the forehead is missing, and the back of the head shows bare skin from the hair edge down to the neck (back).
5. Clothing 4/10: the tee has a raised mock-neck/turtleneck ring instead of a crew neck. The sleeves are puffy balloons with no hem. The shirt hem is a hard horizontal cut. The trousers are baggy joggers bunched at the ankle, not slim jeans with pockets and seams. The shoes are small dark blobs on separate white discs.
6. Colours/materials 5/10: the palette matches (0.91 share), but the skin is lighter and less red-orange than the blueprint. "tau gak?" is printed in red/pink where the blueprint has dark letters with a light outline. The print is a flat decal, not raised embroidery. There is no visible cotton weave or denim twill, and almost no fold ambient occlusion.
7. Pixar style adherence 4/10: the forms are simplified primitives (stick arms, mitten hands, tube trousers), the blush looks like decals, the features look stuck on, and the clothing has no fold sculpting. It reads as a mobile toy/avatar style rather than high-end stylized CGI.
8. Artefacts 5/10 (10 = clean): facial features break the profile outline, the far-cheek blush disc sticks out past the face (three_quarter), there is a bald nape gap (back), the shoe soles look like detached discs (front, back), the hair is noisy, and the shirt/trouser join is an abrupt seam.

## Defects by visual impact
1. Hands have no fingers and taper to points, like claws or mittens (front, back, three_quarter). The blueprint has open, defined hands.
2. Arms are thin uniform cylinders with no elbow, forearm taper or wrist shape, which looks like a mannequin and breaks the style bible's no-mannequin rule (front, back, 3/4).
3. Bald skin patch on the back of the head between the hair edge and the neck (back, also visible in left/right). The blueprint hair covers down to the nape.
4. In profile the facial features stick out: eyeball/brow in front of the face plane, ball nose, lips protruding as a dark blob (right, left). The far-cheek blush disc sticks out past the silhouette (three_quarter).
5. Shoes are about 50% too small and look like blobs on white disc soles. The blueprint has chunky canvas sneakers with laces and rubber soles (front, back, right).
6. Trousers are baggy joggers with gathered ankle cuffs. The blueprint has slim straight white jeans with pockets, fly and side seams and no ankle gathering (front, 3/4).
7. Collar is a raised mock-neck ring on a long thin neck. It should be a flat crew-neck tee collar with a shorter, thicker neck (front, face, back).
8. Blush is flat salmon discs with speckled noise. It should be a soft gradient SSS flush across the cheeks (face, front).
9. Shirt print: second line in red/pink where the blueprint has dark letters with a light outline. The print is flat, not raised embroidery, and sits slightly low and narrow (front, face crop).
10. Sleeves are puffy balloons with no hem band. The shirt has no folds or wrinkles, and its hem is a hard straight cut onto the trousers with no overlap or AO (all views).
11. Hair: grainy, noisy surface with no soft specular highlight. The forelock curl and the side curls in front of the ears are missing (face, front).
12. Skin is a bit desaturated and light compared with the warm orange-brown blueprint skin. SSS cannot be seen at this size (face).
13. Ears are mostly hidden or flattened under the hair. The blueprint ears stick out clearly (face, front).

## Required fixes before re-review
- Sculpt hands with 4 fingers and a thumb (relaxed, slightly curled). Give the arms deltoid, elbow and wrist shape.
- Extend the hair cap down to cover the nape. Add the forelock and side curls. Replace the noise bump with clump-level normals and soft specular.
- Pull the eyes, brows, nose and mouth back into the face surface (blend the nose into the face, sink the lips). Fix the far-cheek blush so it stays inside the outline, or switch to texture-painted blush.
- Scale shoes up about 1.8x into canvas sneakers with a rubber sole wall. Make the trousers slim straight jeans with pockets and seams and no cuff gather.
- Replace the mock-neck with a crew collar and shorten the neck. Add sleeve hems and fold AO, and tuck or overlap the shirt hem.
- Change the print to dark letters with a light outline as in the blueprint, and give it a raised-embroidery bump.
- Re-render on the bible's light-gray backdrop (n_*.png render on white/transparent, not on [0.6,0.6,0.62]).

## Could not verify
- Whether SSS, weave bump, sheen and embroidery bump values are set in the materials (512 px renders; I did not inspect any .blend file).
- Whether the white discs under the shoes are part of the sole mesh or a separate floating object; whether there are interior intersections or holes (e.g. collar to neck, sleeve to arm), since I had no wireframe or close-ups.
- Rig/topology readiness for animation, and whether the body is a single unified mesh (style bible rule).
- Whether the white background in n_*.png is real or alpha shown as white; I could not verify that the lighting rig matches the bible.
- Gate note: framing fails (margin 0.035 < threshold) in every non-front view, but the aggregate gate still reports PASS.
