source VERSION
sed -e 's#{VERSION}#'"${VERSION}"'#g' setup_template.py > setup.py

python3 setup.py build sdist bdist_wheel

cd django_dev
python mk_docs.py

git add --all
git commit -m "Building a new version ${VERSION}"
git tag -a ${VERSION} -m "Building a new version ${VERSION}"
git push
git push origin ${VERSION}
