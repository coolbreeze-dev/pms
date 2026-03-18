# Publishing Harbor

The package is ready to build and bundle locally. Actual npm publishing still requires your npm account and a final decision on package name and license.

## Build and bundle

From the repo root:

```bash
./scripts/build-design-system.sh
./scripts/package-design-system.sh
```

This creates:

- `design-system/artifacts/harbor-design-system-0.1.0.tgz`
- `design-system/artifacts/harbor-design-system-0.1.0.zip`

## Publish to npm

1. Confirm the final package name in `design-system/package.json`.
2. Confirm the final license in `design-system/package.json`.
3. Log into npm:

```bash
./scripts/use-local-node.sh npm login
```

4. Publish from the package directory:

```bash
cd design-system
../scripts/use-local-node.sh npm publish --access public
```

## Notes

- If npm says the package name is already taken, change `name` in `design-system/package.json` and rerun `./scripts/package-design-system.sh`.
- The current package name is `harbor-design-system`.
- The current license is `UNLICENSED`, which is fine for private distribution but should be changed before a public open-source release if you want others to reuse it legally.
